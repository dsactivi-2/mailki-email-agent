import hashlib
import logging
import re

from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import EmailDraft, EmailEvent, KBCompliance, KBSignature, KBTone, KBVip

logger = logging.getLogger(__name__)


def process_new_emails(db: Session) -> list[EmailDraft]:
    """Process unprocessed emails: check KB rules, generate AI draft."""
    unprocessed = db.query(EmailEvent).filter_by(is_processed=False).all()
    drafts = []

    default_tone = db.query(KBTone).filter_by(is_default=True).first()
    default_signature = db.query(KBSignature).filter_by(is_default=True).first()
    vips = db.query(KBVip).all()
    compliance_rules = db.query(KBCompliance).filter_by(is_active=True).all()

    for event in unprocessed:
        priority = _check_vip(event.sender, vips)
        if priority:
            event.priority = priority

        compliance_flags = _check_compliance(event.body_text or "", compliance_rules)

        tone_prompt = default_tone.prompt_template if default_tone else "Antworte professionell und freundlich auf Deutsch."
        signature_text = default_signature.content_text if default_signature else ""

        draft_body = _generate_ai_reply(event, tone_prompt, signature_text, compliance_flags)

        draft = EmailDraft(
            email_event_id=event.id,
            subject=event.subject,
            body_text=draft_body,
            body_hash=_calculate_body_hash(draft_body),
            tone=default_tone.name if default_tone else "default",
            status="pending_approval",
            version=1,
        )
        db.add(draft)
        event.is_processed = True
        drafts.append(draft)

    if drafts:
        db.commit()

    return drafts


def _generate_ai_reply(
    event: EmailEvent,
    tone_prompt: str,
    signature: str,
    compliance_flags: list[str],
) -> str:
    """Generate a reply using OpenAI. Falls back to placeholder if no API key."""
    if not settings.OPENAI_API_KEY:
        logger.warning("No OPENAI_API_KEY set, using placeholder reply")
        return _placeholder_reply(event, signature)

    compliance_note = ""
    if compliance_flags:
        compliance_note = (
            "\n\nACHTUNG - Compliance-Hinweise fuer diese E-Mail:\n"
            + "\n".join(f"- {f}" for f in compliance_flags)
            + "\nBitte beruecksichtige diese Hinweise in der Antwort."
        )

    system_prompt = (
        "Du bist ein professioneller E-Mail-Assistent. "
        f"{tone_prompt}\n"
        "Schreibe NUR den Antworttext, keine Betreffzeile, kein 'Betreff:'.\n"
        "Halte die Antwort kurz und praezise."
        f"{compliance_note}"
    )

    user_prompt = (
        f"Beantworte folgende E-Mail:\n\n"
        f"Von: {event.sender}\n"
        f"Betreff: {event.subject}\n"
        f"Nachricht:\n{event.body_text}\n\n"
        f"---\nAntwort:"
    )

    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=500,
            temperature=0.7,
        )
        reply = response.choices[0].message.content.strip()

        if signature:
            reply += f"\n\n{signature}"

        return reply

    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return _placeholder_reply(event, signature)


def _placeholder_reply(event: EmailEvent, signature: str) -> str:
    body = (
        f"Vielen Dank fuer Ihre Nachricht zum Thema \"{event.subject}\".\n\n"
        f"Wir haben Ihre E-Mail erhalten und melden uns in Kuerze.\n\n"
        f"Mit freundlichen Gruessen,\n"
        f"Mailki Email Agent"
    )
    if signature:
        body += f"\n\n{signature}"
    return body


def _calculate_body_hash(body: str) -> str:
    """Calculate SHA-256 hash of the draft body for tamper detection."""
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def regenerate_draft(db: Session, draft: "EmailDraft", feedback: str) -> "EmailDraft":
    """Regenerate a draft with reviewer feedback incorporated into the tone prompt."""
    event = draft.email_event

    default_tone = db.query(KBTone).filter_by(is_default=True).first()
    default_signature = db.query(KBSignature).filter_by(is_default=True).first()
    compliance_rules = db.query(KBCompliance).filter_by(is_active=True).all()

    compliance_flags = _check_compliance(event.body_text or "", compliance_rules)

    tone_prompt = default_tone.prompt_template if default_tone else "Antworte professionell und freundlich auf Deutsch."
    tone_prompt += f"\n\nWICHTIG - Aenderungswuensche des Reviewers:\n{feedback}"
    signature_text = default_signature.content_text if default_signature else ""

    new_body = _generate_ai_reply(event, tone_prompt, signature_text, compliance_flags)

    draft.body_text = new_body
    draft.body_hash = _calculate_body_hash(new_body)
    draft.version += 1
    draft.status = "pending_approval"
    db.commit()

    return draft


def _check_vip(sender: str, vips: list[KBVip]) -> str | None:
    """Check if sender matches a VIP pattern. Returns priority or None."""
    for vip in vips:
        if vip.email_pattern in sender:
            return vip.priority
    return None


def _check_compliance(body: str, rules: list[KBCompliance]) -> list[str]:
    """Check email body against compliance rules. Returns list of flags."""
    flags = []
    for rule in rules:
        if rule.pattern and re.search(rule.pattern, body, re.IGNORECASE):
            flags.append(f"{rule.rule_name}: {rule.description}")
    return flags
