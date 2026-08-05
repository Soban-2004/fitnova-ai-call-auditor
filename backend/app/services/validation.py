"""Three-layer validation for LLM-produced issue tags (design doc Section 6).

  Layer 1 (Pydantic + enum check): right shape, allowed tag/severity, quote
           non-empty, timestamps within the call.
  Layer 2 (RapidFuzz):   does the quoted text actually appear (allowing minor
           rephrasing) in the transcript near the claimed timestamp?
  Layer 3 (Gemini embeddings): catches paraphrases fuzzy match misses — e.g.
           "offer expires tomorrow" vs "offer ends tomorrow". Only called
           when Layer 2 already failed — a fuzzy pass already validates the
           tag, so skipping the network call in that case costs nothing and
           saves the round-trip + API usage on the common case.

A tag passes if it clears Layer 1 AND at least one of (Layer 2, Layer 3).
Schema-pass-only -> 'needs_review' (stored, surfaced for a human). Schema
fail -> rejected outright, never stored.

Layer 3 used to run locally via sentence-transformers/all-MiniLM-L6-v2. Moved
to Gemini's hosted embedding model (models/gemini-embedding-001) for the
production deploy: sentence-transformers pulls in torch, which is a heavy
enough dependency (~1-2GB installed, 300-500MB+ resident once loaded) that it
risked not fitting a free-tier host's memory limit. Gemini's embedding API
reuses the API key and SDK already in this project (Gemini is already a
fallback LLM provider) — no new account, no new dependency.
"""
import logging
from dataclasses import dataclass

import google.generativeai as genai
import numpy as np
from pydantic import ValidationError
from rapidfuzz import fuzz

from app.config import settings
from app.schemas.analysis import ISSUE_TAG_TYPES, SEVERITIES, IssueTagLLM

logger = logging.getLogger("fitnova.validation")

FUZZY_THRESHOLD = 70
# Calibrated against models/gemini-embedding-001 specifically — a different
# embedding model has a different similarity distribution, so the old 0.75
# (tuned for all-MiniLM-L6-v2) does not carry over. Measured empirically
# against this project's own real transcript segments: a genuine paraphrase
# of a real quote scored ~0.89 cosine similarity; hallucinated/unrelated text
# scored ~0.76. 0.85 sits in the gap between them with margin on both sides.
SEMANTIC_THRESHOLD = 0.85
EMBEDDING_MODEL = "models/gemini-embedding-001"
WINDOW_PADDING_SECS = 10.0
TIMESTAMP_TOLERANCE_SECS = 5.0

_genai_configured = False


def _ensure_genai_configured() -> None:
    """genai.configure() sets global SDK state, not per-instance — safe to
    call more than once (GeminiProvider also calls it), guarded here just to
    skip the redundant call on every single tag."""
    global _genai_configured
    if not _genai_configured:
        if not settings.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set — required for tag validation's semantic layer")
        genai.configure(api_key=settings.GEMINI_API_KEY)
        _genai_configured = True


@dataclass
class ValidationResult:
    status: str  # 'open' | 'needs_review' | 'rejected'
    validation_score: float
    reason: str


def _schema_check(tag: dict, call_duration: float) -> ValidationResult | None:
    """Layer 1. Returns a rejected ValidationResult if invalid, else None
    (caller proceeds to Layer 2/3)."""
    try:
        parsed = IssueTagLLM.model_validate(tag)
    except ValidationError as e:
        return ValidationResult("rejected", 0.0, f"Malformed issue object: {e}")

    if parsed.tag not in ISSUE_TAG_TYPES:
        return ValidationResult("rejected", 0.0, f"Unknown tag: {parsed.tag}")
    if parsed.severity not in SEVERITIES:
        return ValidationResult("rejected", 0.0, f"Invalid severity: {parsed.severity}")
    if not parsed.quote.strip():
        return ValidationResult("rejected", 0.0, "Empty quote")
    if parsed.start_ts < 0 or parsed.end_ts > call_duration + TIMESTAMP_TOLERANCE_SECS:
        return ValidationResult(
            "rejected", 0.0,
            f"Timestamp [{parsed.start_ts}, {parsed.end_ts}] outside call duration {call_duration}s",
        )
    return None


async def validate_tag(tag: dict, transcript_segments: list[dict], call_duration: float) -> ValidationResult:
    """
    Args:
        tag: one issue dict from the LLM's issue-detection response
             ({"tag", "severity", "quote", "start_ts", "end_ts", "reason"}).
        transcript_segments: [{"text", "start_ts", "end_ts"}, ...] — the
             *redacted* transcript already stored for this call.
        call_duration: call duration in seconds.
    """
    schema_failure = _schema_check(tag, call_duration)
    if schema_failure is not None:
        return schema_failure

    start_ts = float(tag.get("start_ts", 0))
    end_ts = float(tag.get("end_ts", 0))
    quote = tag["quote"]

    window_start = max(0, start_ts - WINDOW_PADDING_SECS)
    window_end = end_ts + WINDOW_PADDING_SECS
    window_text = " ".join(
        seg["text"] for seg in transcript_segments
        if seg["end_ts"] >= window_start and seg["start_ts"] <= window_end
    )
    if not window_text:
        # Timestamp pointed nowhere near real content — fall back to the
        # full transcript rather than auto-failing on a bad LLM timestamp.
        window_text = " ".join(seg["text"] for seg in transcript_segments)

    # Layer 2: fuzzy match
    fuzzy_score = fuzz.partial_ratio(quote.lower(), window_text.lower())
    fuzzy_pass = fuzzy_score >= FUZZY_THRESHOLD

    # Layer 3: semantic similarity — skipped if Layer 2 already passed.
    cosine_sim: float | None = None
    if not fuzzy_pass:
        try:
            _ensure_genai_configured()
            result = await genai.embed_content_async(
                model=EMBEDDING_MODEL,
                content=[quote, window_text],
                task_type="SEMANTIC_SIMILARITY",
            )
            e0, e1 = np.array(result["embedding"][0]), np.array(result["embedding"][1])
            cosine_sim = float(np.dot(e0, e1) / (np.linalg.norm(e0) * np.linalg.norm(e1) + 1e-8))
        except Exception as e:
            # A validation-layer outage must never fail the whole call — fall
            # back to fuzzy-only. Worst case this tag lands in needs_review
            # instead of open; it never silently passes or crashes the call.
            logger.warning("Semantic validation call failed, falling back to fuzzy-only: %s", e)

    semantic_pass = cosine_sim is not None and cosine_sim >= SEMANTIC_THRESHOLD
    validation_score = max(fuzzy_score / 100.0, cosine_sim or 0.0)
    semantic_display = f"{cosine_sim:.2f}" if cosine_sim is not None else ("skipped" if fuzzy_pass else "unavailable")

    if fuzzy_pass or semantic_pass:
        return ValidationResult(
            "open", validation_score,
            f"Validated (fuzzy={fuzzy_score}, semantic={semantic_display})",
        )
    return ValidationResult(
        "needs_review", validation_score,
        f"Low match: fuzzy={fuzzy_score}, semantic={semantic_display}",
    )
