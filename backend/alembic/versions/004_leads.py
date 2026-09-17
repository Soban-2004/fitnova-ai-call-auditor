"""Add leads -- the AI voice agent's actual hand-off to a human advisor
(previously just a spoken promise + a saved call, see app/models/lead.py).

Revision ID: 004
Revises: 003
Create Date: 2026-09-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("call_id", UUID(as_uuid=True), sa.ForeignKey("calls.id"), nullable=False),
        sa.Column("customer_name", sa.String(255), nullable=True),
        sa.Column("customer_phone", sa.String(50), nullable=True),
        sa.Column("fitness_goal", sa.Text(), nullable=True),
        sa.Column("health_notes", sa.Text(), nullable=True),
        sa.Column("availability", sa.Text(), nullable=True),
        sa.Column("confirmed_time", sa.Text(), nullable=True),
        sa.Column("assigned_advisor_id", UUID(as_uuid=True), sa.ForeignKey("advisors.id"), nullable=True),
        sa.Column("status", sa.String(20), server_default="NEW"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_leads_status", "leads", ["status"])
    op.create_index("ix_leads_assigned_advisor_id", "leads", ["assigned_advisor_id"])


def downgrade() -> None:
    op.drop_index("ix_leads_assigned_advisor_id", table_name="leads")
    op.drop_index("ix_leads_status", table_name="leads")
    op.drop_table("leads")
