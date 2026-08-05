import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CallScore(Base):
    __tablename__ = "call_scores"
    __table_args__ = (UniqueConstraint("call_id", "version", name="uq_call_score_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("calls.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    base_score: Mapped[float] = mapped_column(Float, nullable=False)
    deductions_total: Mapped[float] = mapped_column(Float, nullable=False)
    final_score: Mapped[int] = mapped_column(Integer, nullable=False)
    trigger: Mapped[str] = mapped_column(String(255), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScoreAuditLog(Base):
    __tablename__ = "score_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("calls.id"), nullable=False)
    from_version: Mapped[int | None] = mapped_column(Integer)
    to_version: Mapped[int | None] = mapped_column(Integer)
    tag_id_affected: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("issue_tags.id"))
    delta: Mapped[int | None] = mapped_column(Integer)
    changed_by: Mapped[str | None] = mapped_column(String(255))
    reason: Mapped[str | None] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
