import uuid

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("calls.id"), nullable=False)
    speaker_label: Mapped[str | None] = mapped_column(String(50))
    speaker_role: Mapped[str | None] = mapped_column(String(20))  # 'advisor' | 'customer' | NULL
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_ts: Mapped[float] = mapped_column(Float, nullable=False)
    end_ts: Mapped[float] = mapped_column(Float, nullable=False)
