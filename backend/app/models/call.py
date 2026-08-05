import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Call(Base):
    __tablename__ = "calls"
    __table_args__ = (UniqueConstraint("source_system", "external_id", name="uq_call_source"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    advisor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("advisors.id"), nullable=False)
    source_system: Mapped[str] = mapped_column(String(50), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    audio_ref: Mapped[str] = mapped_column(Text, nullable=False)
    duration_secs: Mapped[int | None] = mapped_column(Integer)
    called_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), server_default="QUEUED")
    retry_count: Mapped[int] = mapped_column(Integer, server_default="0")
    call_type: Mapped[str | None] = mapped_column(String(20))
    diarization_quality: Mapped[str] = mapped_column(String(20), server_default="good")
    raw_metadata: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    advisor: Mapped["Advisor"] = relationship()
