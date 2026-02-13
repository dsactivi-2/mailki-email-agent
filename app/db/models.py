import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    role = Column(String(50), default="agent")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    mailboxes = relationship("Mailbox", back_populates="user")
    approval_actions = relationship("ApprovalAction", back_populates="reviewer")


class Mailbox(Base):
    __tablename__ = "mailboxes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    email_address = Column(String(255), unique=True, nullable=False, index=True)
    provider = Column(String(50), default="gmail")
    credentials_ref = Column(String(255))
    is_active = Column(Boolean, default=True)
    last_sync_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="mailboxes")
    email_events = relationship("EmailEvent", back_populates="mailbox")


class EmailEvent(Base):
    __tablename__ = "email_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mailbox_id = Column(UUID(as_uuid=True), ForeignKey("mailboxes.id"), nullable=False)
    gmail_message_id = Column(String(255), unique=True, index=True)
    thread_id = Column(String(255), index=True)
    sender = Column(String(255), nullable=False)
    recipient = Column(String(255), nullable=False)
    subject = Column(String(500))
    body_text = Column(Text)
    body_html = Column(Text)
    received_at = Column(DateTime, nullable=False)
    category = Column(String(100))
    priority = Column(String(20), default="normal")
    is_processed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    mailbox = relationship("Mailbox", back_populates="email_events")
    drafts = relationship("EmailDraft", back_populates="email_event")


class EmailDraft(Base):
    __tablename__ = "email_drafts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email_event_id = Column(
        UUID(as_uuid=True), ForeignKey("email_events.id"), nullable=False
    )
    subject = Column(String(500))
    body_text = Column(Text, nullable=False)
    body_html = Column(Text)
    tone = Column(String(50))
    status = Column(
        Enum("draft", "pending_approval", "approved", "rejected", "sent",
             name="draft_status"),
        default="draft",
    )
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    email_event = relationship("EmailEvent", back_populates="drafts")
    approval_actions = relationship("ApprovalAction", back_populates="draft")


class ApprovalAction(Base):
    __tablename__ = "approval_actions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    draft_id = Column(
        UUID(as_uuid=True), ForeignKey("email_drafts.id"), nullable=False
    )
    reviewer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    action = Column(
        Enum("approved", "rejected", "edit_requested", name="approval_action_type"),
        nullable=False,
    )
    comment = Column(Text)
    slack_message_ts = Column(String(100))
    slack_channel_id = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

    draft = relationship("EmailDraft", back_populates="approval_actions")
    reviewer = relationship("User", back_populates="approval_actions")


# --- Knowledge Base Tables ---


class KBSignature(Base):
    __tablename__ = "kb_signatures"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    content_html = Column(Text, nullable=False)
    content_text = Column(Text, nullable=False)
    language = Column(String(10), default="de")
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class KBTone(Base):
    __tablename__ = "kb_tones"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    prompt_template = Column(Text, nullable=False)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class KBVip(Base):
    __tablename__ = "kb_vips"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email_pattern = Column(String(255), nullable=False, index=True)
    name = Column(String(255))
    priority = Column(String(20), default="high")
    special_instructions = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class KBCompliance(Base):
    __tablename__ = "kb_compliance"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_name = Column(String(255), nullable=False, unique=True)
    description = Column(Text)
    pattern = Column(String(500))
    action = Column(String(50), default="flag")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
