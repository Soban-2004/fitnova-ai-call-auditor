"""Add llm_call_logs — per-provider-call telemetry (latency, outcome) for the
3-pass analysis chain and the validation layer's semantic-similarity calls.
See app/services/telemetry.py and app/models/telemetry.py.

Revision ID: 003
Revises: 002
Create Date: 2026-09-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "llm_call_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("purpose", sa.String(50), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("error_type", sa.String(100), nullable=True),
    )
    op.create_index("ix_llm_call_logs_created_at", "llm_call_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_llm_call_logs_created_at", table_name="llm_call_logs")
    op.drop_table("llm_call_logs")
