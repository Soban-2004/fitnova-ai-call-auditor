import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LLMCallLog(Base):
    """One row per LLM provider call (the 3-pass analysis chain in
    services/analysis.py, plus the semantic-validation embedding call in
    services/validation.py) -- routine call-level telemetry: which provider
    in the Groq->Gemini->Ollama fallback chain actually served a call, how
    long it took, and whether it succeeded. See services/telemetry.py, the
    single write path for this table.

    Distinct from Python's stdlib `logging` output already in this app:
    that's free-text, file-based, and lost on a Render restart. This is
    small, structured, queryable rows in the same durable Postgres every
    other table lives in.
    """

    __tablename__ = "llm_call_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    provider: Mapped[str] = mapped_column(String(20), nullable=False)  # "groq" | "gemini" | "ollama"
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    purpose: Mapped[str] = mapped_column(String(50), nullable=False)  # "speaker_id" | "issue_detection" | ...
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)  # "success" | "error"
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    error_type: Mapped[str | None] = mapped_column(String(100))
