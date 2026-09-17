import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Lead(Base):
    """The AI voice agent's actual hand-off mechanism: a lightweight,
    trackable record connecting an AI-qualified call to a specific advisor
    and a follow-up outcome. Deliberately not a CRM -- one table, one
    status enum -- but a real hand-off, not just "the conversation got
    saved somewhere." See routers/voice_agent.py (creates a Lead when a
    qualifying call finishes) and routers/leads.py (assign/status/list).

    PII note: customer_phone is stored RAW here, on purpose -- unlike
    Call.raw_metadata's customer_phone (see services/ingestion.py, always
    redacted before storage), a lead an advisor can't actually call back is
    useless. This is a deliberate, scoped exception for the one place in
    this app where contact info is the whole point, not an oversight --
    but it's worth being explicit that this app has no auth system at all
    (see every router's own docstrings), so nothing gates who can read it.
    Real production use would need that solved first.
    """

    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("calls.id"), nullable=False)
    customer_name: Mapped[str | None] = mapped_column(String(255))
    customer_phone: Mapped[str | None] = mapped_column(String(50))
    fitness_goal: Mapped[str | None] = mapped_column(Text)
    health_notes: Mapped[str | None] = mapped_column(Text)
    availability: Mapped[str | None] = mapped_column(Text)
    confirmed_time: Mapped[str | None] = mapped_column(Text)
    assigned_advisor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("advisors.id"))
    # NEW -> ASSIGNED -> CONTACTED -> TRIAL_BOOKED. Plain string, not an
    # enum column, matching Call.status's own convention in this codebase.
    status: Mapped[str] = mapped_column(String(20), server_default="NEW")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
