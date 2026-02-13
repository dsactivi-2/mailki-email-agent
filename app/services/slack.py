import hashlib
import hmac
import json
import time

import httpx

from app.core.config import settings
from app.db.models import EmailDraft, EmailEvent


async def post_draft_for_approval(draft: EmailDraft, event: EmailEvent) -> dict:
    """Post a draft to #mailki-approvals with Approve/Reject buttons."""
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
            "text": {
                "type": "mrkdwn",
                "text": f"*Original-Nachricht (Auszug):*\n>{event.body_text[:300]}..."
                if len(event.body_text or "") > 300
                else f"*Original-Nachricht:*\n>{event.body_text or '(leer)'}",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Entwurf:*\n```{draft.body_text}```",
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
            ],
        },
    ]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {settings.SLACK_BOT_TOKEN}"},
            json={
                "channel": settings.SLACK_APPROVAL_CHANNEL,
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
