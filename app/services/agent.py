from sqlalchemy.orm import Session

from app.db.models import EmailDraft, EmailEvent


def process_new_emails(db: Session) -> list[EmailDraft]:
    """Process unprocessed emails and create simple drafts.

    MVP: generates a placeholder reply. Will be replaced with AI agent later.
    """
    unprocessed = db.query(EmailEvent).filter_by(is_processed=False).all()
    drafts = []

    for event in unprocessed:
        draft_body = (
            f"Vielen Dank fuer Ihre Nachricht zum Thema \"{event.subject}\".\n\n"
            f"Wir haben Ihre E-Mail erhalten und melden uns in Kuerze.\n\n"
            f"Mit freundlichen Gruessen,\n"
            f"Mailki Email Agent"
        )

        draft = EmailDraft(
            email_event_id=event.id,
            subject=event.subject,
            body_text=draft_body,
            tone="formal",
            status="pending_approval",
            version=1,
        )
        db.add(draft)

        event.is_processed = True
        drafts.append(draft)

    if drafts:
        db.commit()

    return drafts
