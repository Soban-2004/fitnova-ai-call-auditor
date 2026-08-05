"""Orchestrates the 3-pass LLM analysis (design doc Section 5):
  Call #1: speaker role identification
  Call #2: issue detection
  Call #3: dimension ratings

All calls run at temperature=0 for determinism and go through the provider
fallback chain (Groq -> Gemini -> Ollama Cloud) so a single provider outage
doesn't fail the call. Every result is validated against its Pydantic schema
(schemas/analysis.py) before the caller (processor.py) touches it.
"""
import logging

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.base import LLMProviderError
from app.llm.factory import get_provider_chain
from app.models.analysis import PromptVersion
from app.schemas.analysis import DimensionRatingResult, IssueDetectionResult, SpeakerIdResult

logger = logging.getLogger("fitnova.analysis")


class NoActivePromptError(Exception):
    pass


async def get_active_prompt(session: AsyncSession, prompt_type: str) -> PromptVersion:
    prompt = await session.scalar(
        select(PromptVersion)
        .where(PromptVersion.prompt_type == prompt_type, PromptVersion.is_active.is_(True))
        .order_by(PromptVersion.version.desc())
    )
    if prompt is None:
        raise NoActivePromptError(f"No active prompt_version for prompt_type={prompt_type!r}")
    return prompt


def format_transcript(segments: list[dict], use_labels: bool = True) -> str:
    """Renders transcript segments as `[12.3s] Speaker 0: text` lines (before
    speaker ID) or `[12.3s] Advisor: text` (after roles are known).

    Args:
        segments: [{"speaker_label", "speaker_role", "text", "start_ts", ...}]
        use_labels: True -> use speaker_label (Speaker 0/1), for Call #1.
                    False -> use speaker_role if set, for Calls #2/#3.
    """
    lines = []
    for seg in segments:
        if use_labels:
            speaker = seg.get("speaker_label") or "Unknown"
        else:
            speaker = (seg.get("speaker_role") or seg.get("speaker_label") or "unknown").capitalize()
        lines.append(f"[{seg['start_ts']:.1f}s] {speaker}: {seg['text']}")
    return "\n".join(lines)


async def complete_with_fallback(system_prompt: str, user_message: str, temperature: float = 0.0) -> dict:
    """Tries each provider in the fallback chain in order, returning the
    first successful parsed-JSON response. Raises LLMProviderError only if
    every provider in the chain fails."""
    chain = get_provider_chain()
    if not chain:
        raise LLMProviderError("No LLM providers are configured")

    last_error: Exception | None = None
    for name, provider in chain:
        try:
            return await provider.complete(system_prompt, user_message, temperature)
        except Exception as e:
            logger.warning("LLM provider %s failed, trying next in chain: %s", name, e)
            last_error = e
    raise LLMProviderError(f"All LLM providers in the fallback chain failed. Last error: {last_error}")


async def identify_speakers(segments: list[dict], system_prompt: str) -> SpeakerIdResult:
    transcript = format_transcript(segments, use_labels=True)
    raw = await complete_with_fallback(system_prompt, transcript)
    try:
        return SpeakerIdResult.model_validate(raw)
    except ValidationError as e:
        raise LLMProviderError(f"Speaker ID response failed schema validation: {e}") from e


async def detect_issues(segments: list[dict], system_prompt: str) -> IssueDetectionResult:
    transcript = format_transcript(segments, use_labels=False)
    raw = await complete_with_fallback(system_prompt, transcript)
    try:
        return IssueDetectionResult.model_validate(raw)
    except ValidationError as e:
        raise LLMProviderError(f"Issue detection response failed schema validation: {e}") from e


async def rate_dimensions(segments: list[dict], system_prompt: str) -> DimensionRatingResult:
    transcript = format_transcript(segments, use_labels=False)
    raw = await complete_with_fallback(system_prompt, transcript)
    try:
        return DimensionRatingResult.model_validate(raw)
    except ValidationError as e:
        raise LLMProviderError(f"Dimension rating response failed schema validation: {e}") from e
