import logging

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import EmailDraft, EmailEvent, Mailbox
from app.services.agent import process_new_emails
from app.services.gmail import fetch_new_emails
from app.services.slack import post_draft_for_approval

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/ping")
def ping():
    return {"message": "pong"}


@router.post("/ingest")
def ingest_emails(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Trigger email ingestion for all active mailboxes."""
    mailboxes = db.query(Mailbox).filter_by(is_active=True).all()
    total_new = 0
    errors = []
    for mailbox in mailboxes:
        try:
            new_events = fetch_new_emails(db, mailbox)
            total_new += len(new_events)
        except Exception as e:
            logger.error(f"Ingestion error for mailbox {mailbox.email_address}: {e}")
            errors.append({"mailbox": mailbox.email_address, "error": str(e)})

    if total_new > 0:
        background_tasks.add_task(_process_and_notify, db)

    return {"status": "ok", "new_emails": total_new, "errors": errors}


@router.post("/process")
def process_emails(db: Session = Depends(get_db)):
    """Process unprocessed emails and create drafts."""
    drafts = process_new_emails(db)
    results = []
    for draft in drafts:
        results.append({
            "draft_id": str(draft.id),
            "subject": draft.subject,
            "status": draft.status,
        })
    return {"status": "ok", "drafts_created": len(drafts), "drafts": results}


@router.post("/notify")
async def notify_pending_drafts(db: Session = Depends(get_db)):
    """Send all pending drafts to Slack for approval."""
    drafts = db.query(EmailDraft).filter_by(status="pending_approval").all()
    notified = 0
    for draft in drafts:
        event = db.query(EmailEvent).filter_by(id=draft.email_event_id).first()
        if event:
            try:
                await post_draft_for_approval(draft, event)
                notified += 1
            except Exception as e:
                logger.error(f"Slack notification error for draft {draft.id}: {e}")
    return {"status": "ok", "notified": notified}


@router.get("/drafts")
def list_drafts(status: str = None, db: Session = Depends(get_db)):
    """List drafts, optionally filtered by status."""
    query = db.query(EmailDraft)
    if status:
        query = query.filter_by(status=status)
    drafts = query.order_by(EmailDraft.created_at.desc()).limit(50).all()
    return [
        {
            "id": str(d.id),
            "subject": d.subject,
            "status": d.status,
            "tone": d.tone,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in drafts
    ]


@router.get("/events")
def list_events(is_processed: bool = None, db: Session = Depends(get_db)):
    """List email events."""
    query = db.query(EmailEvent)
    if is_processed is not None:
        query = query.filter_by(is_processed=is_processed)
    events = query.order_by(EmailEvent.received_at.desc()).limit(50).all()
    return [
        {
            "id": str(e.id),
            "sender": e.sender,
            "subject": e.subject,
            "priority": e.priority,
            "is_processed": e.is_processed,
            "received_at": e.received_at.isoformat() if e.received_at else None,
        }
        for e in events
    ]


async def _process_and_notify(db: Session):
    """Background: process emails and notify Slack."""
    drafts = process_new_emails(db)
    for draft in drafts:
        event = db.query(EmailEvent).filter_by(id=draft.email_event_id).first()
        if event:
            try:
                await post_draft_for_approval(draft, event)
            except Exception as e:
                logger.error(f"Background notify error: {e}")
