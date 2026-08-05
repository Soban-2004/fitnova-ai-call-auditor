"""Initial schema — org hierarchy, calls, transcripts, analysis outputs, scoring.

Revision ID: 001
Revises:
Create Date: 2026-08-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # --- Org hierarchy ---
    op.create_table(
        "orgs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "teams",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "advisors",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Calls ---
    op.create_table(
        "calls",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("advisor_id", UUID(as_uuid=True), sa.ForeignKey("advisors.id"), nullable=False),
        sa.Column("source_system", sa.String(50), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("audio_ref", sa.Text, nullable=False),
        sa.Column("duration_secs", sa.Integer),
        sa.Column("called_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), server_default="QUEUED"),
        sa.Column("retry_count", sa.Integer, server_default="0"),
        sa.Column("call_type", sa.String(20)),
        sa.Column("diarization_quality", sa.String(20), server_default="good"),
        sa.Column("raw_metadata", JSONB),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("source_system", "external_id", name="uq_call_source"),
    )
    op.create_index("idx_calls_status", "calls", ["status"])
    op.create_index("idx_calls_advisor", "calls", ["advisor_id"])

    # --- Transcripts ---
    op.create_table(
        "transcript_segments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("call_id", UUID(as_uuid=True), sa.ForeignKey("calls.id"), nullable=False),
        sa.Column("speaker_label", sa.String(50)),
        sa.Column("speaker_role", sa.String(20)),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("start_ts", sa.Float, nullable=False),
        sa.Column("end_ts", sa.Float, nullable=False),
    )
    op.create_index("idx_segments_call", "transcript_segments", ["call_id"])

    # --- Prompt versions ---
    op.create_table(
        "prompt_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("prompt_type", sa.String(50), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("system_prompt", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("prompt_type", "version", name="uq_prompt_type_version"),
    )

    # --- Analysis outputs ---
    op.create_table(
        "issue_tags",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("call_id", UUID(as_uuid=True), sa.ForeignKey("calls.id"), nullable=False),
        sa.Column("prompt_version_id", UUID(as_uuid=True), sa.ForeignKey("prompt_versions.id")),
        sa.Column("tag_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("quote", sa.Text, nullable=False),
        sa.Column("start_ts", sa.Float),
        sa.Column("end_ts", sa.Float),
        sa.Column("reason", sa.Text),
        sa.Column("validation_score", sa.Float),
        sa.Column("status", sa.String(20), server_default="open"),
        sa.Column("contest_reason", sa.Text),
        sa.Column("review_comment", sa.Text),
        sa.Column("reviewed_by", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_tags_call", "issue_tags", ["call_id"])
    op.create_index("idx_tags_status", "issue_tags", ["status"])

    op.create_table(
        "dimension_ratings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("call_id", UUID(as_uuid=True), sa.ForeignKey("calls.id"), nullable=False),
        sa.Column("prompt_version_id", UUID(as_uuid=True), sa.ForeignKey("prompt_versions.id")),
        sa.Column("dimension", sa.String(50), nullable=False),
        sa.Column("score", sa.Integer, nullable=False),
        sa.Column("evidence", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("score >= 0 AND score <= 10", name="ck_dimension_score_range"),
    )

    # --- Scores ---
    op.create_table(
        "call_scores",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("call_id", UUID(as_uuid=True), sa.ForeignKey("calls.id"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("base_score", sa.Float, nullable=False),
        sa.Column("deductions_total", sa.Float, nullable=False),
        sa.Column("final_score", sa.Integer, nullable=False),
        sa.Column("trigger", sa.String(255), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("call_id", "version", name="uq_call_score_version"),
    )
    op.create_index("idx_scores_call_version", "call_scores", ["call_id", sa.text("version DESC")])

    op.create_table(
        "score_audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("call_id", UUID(as_uuid=True), sa.ForeignKey("calls.id"), nullable=False),
        sa.Column("from_version", sa.Integer),
        sa.Column("to_version", sa.Integer),
        sa.Column("tag_id_affected", UUID(as_uuid=True), sa.ForeignKey("issue_tags.id")),
        sa.Column("delta", sa.Integer),
        sa.Column("changed_by", sa.String(255)),
        sa.Column("reason", sa.Text),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    for table in [
        "score_audit_log",
        "call_scores",
        "dimension_ratings",
        "issue_tags",
        "prompt_versions",
        "transcript_segments",
        "calls",
        "advisors",
        "teams",
        "orgs",
    ]:
        op.drop_table(table)
