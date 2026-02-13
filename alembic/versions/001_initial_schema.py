"""Initial schema with all models including MVP fields.

Revision ID: 001_initial
Revises:
Create Date: 2026-02-13
"""

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), server_default="agent"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Mailboxes
    op.create_table(
        "mailboxes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("email_address", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("provider", sa.String(50), server_default="gmail"),
        sa.Column("credentials_ref", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Email Events
    op.create_table(
        "email_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("mailbox_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("mailboxes.id"), nullable=False),
        sa.Column("gmail_message_id", sa.String(255), unique=True, index=True),
        sa.Column("thread_id", sa.String(255), index=True),
        sa.Column("sender", sa.String(255), nullable=False),
        sa.Column("recipient", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(500), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("cc", sa.Text(), nullable=True),
        sa.Column("bcc", sa.Text(), nullable=True),
        sa.Column("priority", sa.String(20), server_default="normal"),
        sa.Column("is_processed", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Draft status enum
    draft_status = postgresql.ENUM(
        "draft", "pending_approval", "approved", "rejected", "sent",
        name="draft_status",
        create_type=True,
    )
    draft_status.create(op.get_bind(), checkfirst=True)

    # Email Drafts
    op.create_table(
        "email_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("email_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("email_events.id"), nullable=False),
        sa.Column("subject", sa.String(500), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("tone", sa.String(50), nullable=True),
        sa.Column("gmail_draft_id", sa.String(255), nullable=True, index=True),
        sa.Column("body_hash", sa.String(64), nullable=True),
        sa.Column("status", draft_status, server_default="draft"),
        sa.Column("version", sa.Integer(), server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Approval action enum
    approval_action_type = postgresql.ENUM(
        "approved", "rejected", "edit_requested",
        name="approval_action_type",
        create_type=True,
    )
    approval_action_type.create(op.get_bind(), checkfirst=True)

    # Approval Actions
    op.create_table(
        "approval_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("draft_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("email_drafts.id"), nullable=False),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", approval_action_type, nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("slack_message_ts", sa.String(100), nullable=True),
        sa.Column("slack_channel_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Knowledge Base tables
    op.create_table(
        "kb_signatures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("content_html", sa.Text(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("language", sa.String(10), server_default="de"),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "kb_tones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("prompt_template", sa.Text(), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "kb_vips",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("email_pattern", sa.String(255), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("priority", sa.String(20), server_default="high"),
        sa.Column("special_instructions", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "kb_compliance",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("rule_name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("pattern", sa.String(500), nullable=True),
        sa.Column("action", sa.String(50), server_default="flag"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("kb_compliance")
    op.drop_table("kb_vips")
    op.drop_table("kb_tones")
    op.drop_table("kb_signatures")
    op.drop_table("approval_actions")
    op.drop_table("email_drafts")
    op.drop_table("email_events")
    op.drop_table("mailboxes")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS draft_status")
    op.execute("DROP TYPE IF EXISTS approval_action_type")
