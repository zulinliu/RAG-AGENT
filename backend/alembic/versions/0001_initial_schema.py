"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-14

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str]] = None
depends_on: Union[str, Sequence[str]] = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("username", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=True),
        sa.Column("avatar_url", sa.Text, nullable=True),
        sa.Column("role", sa.String(32), nullable=False, server_default="viewer"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- projects ---
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("icon_url", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
    )

    # --- user_projects (many-to-many with role) ---
    op.create_table(
        "user_projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("role", sa.String(32), nullable=False, server_default="project_member"),
    )
    op.create_unique_constraint("uq_user_projects_user_id_project_id", "user_projects", ["user_id", "project_id"])

    # --- data_sources ---
    op.create_table(
        "data_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("config", postgresql.JSONB, server_default="{}", nullable=True),
        sa.Column("sync_status", sa.String(32), server_default="idle", nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("last_sync_error", sa.Text, nullable=True),
    )

    # --- documents ---
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("data_source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("data_sources.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(256), nullable=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("file_path", sa.Text, nullable=True),
        sa.Column("file_size", sa.Integer, nullable=True),
        sa.Column("mime_type", sa.String(128), nullable=True),
        sa.Column("file_type", sa.String(32), nullable=True),
        sa.Column("checksum", sa.String(64), nullable=True, index=True),
        sa.Column("author", sa.String(256), nullable=True),
        sa.Column("metadata", postgresql.JSONB, server_default="{}", nullable=True),
        sa.Column("status", sa.String(32), server_default="pending", nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
    )
    op.create_index("ix_documents_status", "documents", ["status"])

    # --- document_chunks ---
    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("chunk_type", sa.String(32), server_default="paragraph", nullable=True),
        sa.Column("char_count", sa.Integer, server_default="0", nullable=True),
        sa.Column("metadata", postgresql.JSONB, server_default="{}", nullable=True),
        sa.Column("hierarchy", postgresql.JSONB, nullable=True),
        sa.Column("parent_title", sa.String(512), nullable=True),
        sa.Column("vector_id", sa.String(128), nullable=True),
        sa.Column("es_id", sa.String(128), nullable=True),
    )

    # --- conversations ---
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(256), nullable=True),
    )
    op.create_index("ix_conversations_user_project", "conversations", ["user_id", "project_id", "updated_at"])

    # --- messages ---
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("sources", postgresql.JSONB, nullable=True),
        sa.Column("feedback", sa.String(16), server_default="none", nullable=True),
        sa.Column("confidence_score", sa.Float, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
    )
    op.create_index("ix_messages_conversation_created", "messages", ["conversation_id", "created_at"])


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("data_sources")
    op.drop_table("user_projects")
    op.drop_table("projects")
    op.drop_table("users")
