import hashlib
import hmac
import time

import httpx

from app.core.config import settings
from app.db.models import EmailDraft, EmailEvent


async def post_draft_for_approval(draft: EmailDraft, event: EmailEvent) -> dict:
    """Post a draft via DM to the approver with Approve/Reject/Request Changes buttons."""

    # Build To/CC/BCC display
    recipients_fields = [
        {"type": "mrkdwn", "text": f"*An:*\n{event.recipient}"},
    ]
    if event.cc:
        recipients_fields.append({"type": "mrkdwn", "text": f"*CC:*\n{event.cc}"})
    if event.bcc:
        recipients_fields.append({"type": "mrkdwn", "text": f"*BCC:*\n{event.bcc}"})

    original_text = event.body_text or "(leer)"
    if len(original_text) > 300:
        original_text = original_text[:300] + "..."

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Neuer E-Mail-Entwurf zur Freigabe"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Von:*\n{event.sender}"},
                {"type": "mrkdwn", "text": f"*Betreff:*\n{event.subject}"},
            ],
        },
        {
            "type": "section",
            "fields": recipients_fields,
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Original-Nachricht:*\n>{original_text}",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Entwurf (v{draft.version}):*\n```{draft.body_text}```",
            },
        },
        {
            "type": "actions",
            "block_id": f"approval_{draft.id}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve"},
                    "style": "primary",
                    "action_id": "approve_draft",
                    "value": str(draft.id),
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Reject"},
                    "style": "danger",
                    "action_id": "reject_draft",
                    "value": str(draft.id),
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Request Changes"},
                    "action_id": "request_changes_draft",
                    "value": str(draft.id),
                },
            ],
        },
    ]

    async with httpx.AsyncClient() as client:
        # Open DM channel with approver
        dm_resp = await client.post(
            "https://slack.com/api/conversations.open",
            headers={"Authorization": f"Bearer {settings.SLACK_BOT_TOKEN}"},
            json={"users": settings.SLACK_APPROVER_USER_ID},
        )
        dm_data = dm_resp.json()
        dm_channel_id = dm_data.get("channel", {}).get("id")

        if not dm_channel_id:
            raise ValueError(f"Could not open DM with approver: {dm_data}")

        # Send message to DM
        resp = await client.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {settings.SLACK_BOT_TOKEN}"},
            json={
                "channel": dm_channel_id,
                "text": f"Neuer Entwurf fuer: {event.subject}",
                "blocks": blocks,
            },
        )
        return resp.json()


def verify_slack_signature(body: bytes, timestamp: str, signature: str) -> bool:
    """Verify that a request actually came from Slack."""
    if abs(time.time() - float(timestamp)) > 60 * 5:
        return False
    sig_basestring = f"v0:{timestamp}:{body.decode()}"
    my_signature = (
        "v0="
        + hmac.new(
            settings.SLACK_SIGNING_SECRET.encode(),
            sig_basestring.encode(),
            hashlib.sha256,
        ).hexdigest()
    )
    return hmac.compare_digest(my_signature, signature)
