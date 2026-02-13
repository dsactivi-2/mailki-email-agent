import asyncio
import logging

from app.core.config import settings
from app.db.base import SessionLocal
from app.db.models import EmailEvent, Mailbox
from app.services.agent import process_new_emails
from app.services.gmail import (
    create_gmail_draft,
    fetch_new_emails,
    get_or_create_label,
    set_label,
)
from app.services.slack import post_draft_for_approval

logger = logging.getLogger(__name__)


async def poll_emails_loop():
    """Background loop: fetch emails, create drafts, notify Slack."""
    interval = settings.POLL_INTERVAL_MINUTES * 60
    logger.info(f"Email polling started, interval: {settings.POLL_INTERVAL_MINUTES} min")

    while True:
        try:
            db = SessionLocal()
            mailboxes = db.query(Mailbox).filter_by(is_active=True).all()

            total_new = 0
            for mailbox in mailboxes:
                if not mailbox.credentials_ref:
                    continue
                try:
                    new_events = fetch_new_emails(db, mailbox)
                    total_new += len(new_events)
                except Exception as e:
                    logger.error(f"Error fetching emails for {mailbox.email_address}: {e}")

            if total_new > 0:
                logger.info(f"Fetched {total_new} new emails, processing...")
                drafts = process_new_emails(db)
                for draft in drafts:
                    event = db.query(EmailEvent).filter_by(id=draft.email_event_id).first()
                    if event:
                        mailbox_id = str(event.mailbox_id)

                        # Create Gmail draft and set label
                        try:
                            gmail_draft_id = create_gmail_draft(
                                mailbox_id=mailbox_id,
                                thread_id=event.thread_id,
                                to=event.sender,
                                subject=event.subject,
                                body=draft.body_text,
                            )
                            draft.gmail_draft_id = gmail_draft_id
                            db.commit()
                        except Exception as e:
                            logger.error(f"Gmail draft creation failed for draft {draft.id}: {e}")

                        try:
                            label_id = get_or_create_label(mailbox_id, "needs_approval")
                            set_label(mailbox_id, event.gmail_message_id, label_id)
                        except Exception as e:
                            logger.error(f"Label setting failed for event {event.id}: {e}")

                        # Send Slack DM
                        try:
                            await post_draft_for_approval(draft, event)
                        except Exception as e:
                            logger.error(f"Error notifying Slack for draft {draft.id}: {e}")

            db.close()

        except Exception as e:
            logger.error(f"Polling loop error: {e}")

        await asyncio.sleep(interval)
