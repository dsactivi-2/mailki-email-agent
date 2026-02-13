import json

from fastapi import APIRouter, Depends, Header, Request, Response
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import ApprovalAction, EmailDraft, EmailEvent
from app.services.gmail import send_reply
from app.services.slack import verify_slack_signature

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

    if payload.get("type") != "block_actions":
        return {"ok": True}

    action = payload["actions"][0]
    action_id = action["action_id"]
    draft_id = action["value"]
    slack_user = payload["user"]["id"]

    draft = db.query(EmailDraft).filter_by(id=draft_id).first()
    if not draft:
        return {"ok": False, "error": "Draft not found"}

    if action_id == "approve_draft":
        draft.status = "approved"

        approval = ApprovalAction(
            draft_id=draft.id,
            reviewer_id=draft.email_event.mailbox.user_id,
            action="approved",
            slack_message_ts=payload.get("message", {}).get("ts"),
            slack_channel_id=payload.get("channel", {}).get("id"),
        )
        db.add(approval)

        event = draft.email_event
        try:
            send_reply(
                mailbox_id=str(event.mailbox_id),
                thread_id=event.thread_id,
                to=event.sender,
                subject=event.subject,
                body=draft.body_text,
            )
            draft.status = "sent"
        except Exception as e:
            draft.status = "approved"
            db.commit()
            return {"ok": False, "error": str(e)}

    elif action_id == "reject_draft":
        draft.status = "rejected"

        approval = ApprovalAction(
            draft_id=draft.id,
            reviewer_id=draft.email_event.mailbox.user_id,
            action="rejected",
            slack_message_ts=payload.get("message", {}).get("ts"),
            slack_channel_id=payload.get("channel", {}).get("id"),
        )
        db.add(approval)

    db.commit()
    return {"ok": True}
