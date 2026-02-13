import json
import logging

import httpx
from fastapi import APIRouter, Depends, Header, Request, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import get_db
from app.db.models import ApprovalAction, EmailDraft, EmailEvent
from app.services.agent import _calculate_body_hash, regenerate_draft
from app.services.gmail import (
    check_thread_has_label,
    create_gmail_draft,
    get_or_create_label,
    remove_label,
    send_reply,
    set_label,
)
from app.services.slack import post_draft_for_approval, verify_slack_signature

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/slack/interactions")
async def handle_slack_interaction(
    request: Request,
    db: Session = Depends(get_db),
    x_slack_request_timestamp: str = Header(default=""),
    x_slack_signature: str = Header(default=""),
):
    body = await request.body()

    if not verify_slack_signature(body, x_slack_request_timestamp, x_slack_signature):
        return Response(status_code=403, content="Invalid signature")

    form_data = await request.form()
    payload = json.loads(form_data.get("payload", "{}"))
    payload_type = payload.get("type")

    # Handle button actions
    if payload_type == "block_actions":
        return await _handle_block_actions(payload, db)

    # Handle modal submissions
    if payload_type == "view_submission":
        return await _handle_view_submission(payload, db)

    return {"ok": True}


async def _handle_block_actions(payload: dict, db: Session) -> dict:
    action = payload["actions"][0]
    action_id = action["action_id"]
    draft_id = action["value"]
    slack_user = payload["user"]["id"]

    draft = db.query(EmailDraft).filter_by(id=draft_id).first()
    if not draft:
        return {"ok": False, "error": "Draft not found"}

    event = draft.email_event

    if action_id == "approve_draft":
        return await _handle_approve(draft, event, payload, db)

    elif action_id == "reject_draft":
        return await _handle_reject(draft, event, payload, db)

    elif action_id == "request_changes_draft":
        return await _handle_request_changes(draft, payload)

    return {"ok": True}


async def _handle_approve(draft: EmailDraft, event: EmailEvent, payload: dict, db: Session) -> dict:
    mailbox_id = str(event.mailbox_id)

    # 1. Hash verification: ensure draft body hasn't been tampered with
    current_hash = _calculate_body_hash(draft.body_text)
    if draft.body_hash and current_hash != draft.body_hash:
        logger.warning(f"Hash mismatch for draft {draft.id} — body was modified outside the flow")
        return {"ok": False, "error": "Draft body was modified. Please review again."}

    # 2. Duplicate-send check: ensure we haven't already sent on this thread
    try:
        sent_label_id = get_or_create_label(mailbox_id, "sent_by_agent")
        if check_thread_has_label(mailbox_id, event.thread_id, sent_label_id):
            logger.warning(f"Thread {event.thread_id} already has sent_by_agent label — duplicate send prevented")
            draft.status = "sent"
            db.commit()
            return {"ok": False, "error": "Email already sent for this thread."}
    except Exception as e:
        logger.error(f"Label check failed: {e}")

    # 3. Send the email
    draft.status = "approved"
    approval = ApprovalAction(
        draft_id=draft.id,
        reviewer_id=draft.email_event.mailbox.user_id,
        action="approved",
        slack_message_ts=payload.get("message", {}).get("ts"),
        slack_channel_id=payload.get("channel", {}).get("id"),
    )
    db.add(approval)

    try:
        send_reply(
            mailbox_id=mailbox_id,
            thread_id=event.thread_id,
            to=event.sender,
            subject=event.subject,
            body=draft.body_text,
        )
        draft.status = "sent"

        # 4. Label management: set sent_by_agent, remove needs_approval
        try:
            sent_label_id = get_or_create_label(mailbox_id, "sent_by_agent")
            set_label(mailbox_id, event.gmail_message_id, sent_label_id)

            needs_approval_label_id = get_or_create_label(mailbox_id, "needs_approval")
            remove_label(mailbox_id, event.gmail_message_id, needs_approval_label_id)
        except Exception as e:
            logger.error(f"Label update after send failed: {e}")

    except Exception as e:
        draft.status = "approved"
        db.commit()
        return {"ok": False, "error": str(e)}

    db.commit()
    return {"ok": True}


async def _handle_reject(draft: EmailDraft, event: EmailEvent, payload: dict, db: Session) -> dict:
    draft.status = "rejected"

    approval = ApprovalAction(
        draft_id=draft.id,
        reviewer_id=draft.email_event.mailbox.user_id,
        action="rejected",
        slack_message_ts=payload.get("message", {}).get("ts"),
        slack_channel_id=payload.get("channel", {}).get("id"),
    )
    db.add(approval)

    # Remove needs_approval label
    try:
        mailbox_id = str(event.mailbox_id)
        needs_approval_label_id = get_or_create_label(mailbox_id, "needs_approval")
        remove_label(mailbox_id, event.gmail_message_id, needs_approval_label_id)
    except Exception as e:
        logger.error(f"Label removal on reject failed: {e}")

    db.commit()
    return {"ok": True}


async def _handle_request_changes(draft: EmailDraft, payload: dict) -> dict:
    """Open a Slack modal for the reviewer to enter change feedback."""
    trigger_id = payload.get("trigger_id")
    if not trigger_id:
        return {"ok": False, "error": "No trigger_id in payload"}

    modal = {
        "type": "modal",
        "callback_id": f"changes_modal_{draft.id}",
        "title": {"type": "plain_text", "text": "Aenderungen anfordern"},
        "submit": {"type": "plain_text", "text": "Absenden"},
        "close": {"type": "plain_text", "text": "Abbrechen"},
        "blocks": [
            {
                "type": "input",
                "block_id": "feedback_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "feedback_input",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Beschreibe die gewuenschten Aenderungen...",
                    },
                },
                "label": {"type": "plain_text", "text": "Feedback / Aenderungswuensche"},
            }
        ],
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://slack.com/api/views.open",
            headers={"Authorization": f"Bearer {settings.SLACK_BOT_TOKEN}"},
            json={"trigger_id": trigger_id, "view": modal},
        )
        result = resp.json()
        if not result.get("ok"):
            logger.error(f"Failed to open modal: {result}")

    return {"ok": True}


async def _handle_view_submission(payload: dict, db: Session) -> dict:
    """Handle the modal submission with feedback for re-drafting."""
    callback_id = payload.get("view", {}).get("callback_id", "")

    if not callback_id.startswith("changes_modal_"):
        return {"ok": True}

    draft_id = callback_id.replace("changes_modal_", "")
    draft = db.query(EmailDraft).filter_by(id=draft_id).first()
    if not draft:
        return {"ok": False, "error": "Draft not found"}

    # Extract feedback from modal values
    values = payload.get("view", {}).get("state", {}).get("values", {})
    feedback = (
        values.get("feedback_block", {})
        .get("feedback_input", {})
        .get("value", "")
    )

    if not feedback:
        return {"ok": False, "error": "No feedback provided"}

    event = draft.email_event
    slack_user = payload.get("user", {}).get("id", "")

    # 1. Record the edit request
    approval = ApprovalAction(
        draft_id=draft.id,
        reviewer_id=draft.email_event.mailbox.user_id,
        action="edit_requested",
        comment=feedback,
    )
    db.add(approval)

    # 2. Regenerate draft with feedback
    try:
        draft = regenerate_draft(db, draft, feedback)
    except Exception as e:
        logger.error(f"Draft regeneration failed: {e}")
        db.commit()
        return {"response_action": "errors", "errors": {"feedback_block": f"Fehler: {e}"}}

    # 3. Create new Gmail draft
    try:
        new_gmail_draft_id = create_gmail_draft(
            mailbox_id=str(event.mailbox_id),
            thread_id=event.thread_id,
            to=event.sender,
            subject=event.subject,
            body=draft.body_text,
        )
        draft.gmail_draft_id = new_gmail_draft_id
        db.commit()
    except Exception as e:
        logger.error(f"Gmail draft creation after changes failed: {e}")

    # 4. Send new DM with updated draft
    try:
        await post_draft_for_approval(draft, event)
    except Exception as e:
        logger.error(f"Slack DM for updated draft failed: {e}")

    # Return empty body to close the modal
    return {}
