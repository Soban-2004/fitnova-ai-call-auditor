import pytest

from app.services.validation import SEMANTIC_THRESHOLD, validate_tag

SEGMENTS = [
    {"text": "You need to decide today or this price goes away", "start_ts": 120.0, "end_ts": 125.0},
    {"text": "I understand that's a big commitment", "start_ts": 125.0, "end_ts": 128.0},
]
CALL_DURATION = 180.0


def _base_tag(**overrides):
    tag = {
        "tag": "PRESSURE_SELLING",
        "severity": "critical",
        "quote": "You need to decide today or this price goes away",
        "start_ts": 120.0,
        "end_ts": 125.0,
        "reason": "Creates artificial urgency",
    }
    tag.update(overrides)
    return tag


@pytest.mark.asyncio
async def test_valid_exact_quote_passes_open():
    result = await validate_tag(_base_tag(), SEGMENTS, CALL_DURATION)
    assert result.status == "open"
    assert result.validation_score >= 0.7


@pytest.mark.asyncio
async def test_unknown_tag_type_rejected():
    result = await validate_tag(_base_tag(tag="MADE_UP_TAG"), SEGMENTS, CALL_DURATION)
    assert result.status == "rejected"
    assert "Unknown tag" in result.reason


@pytest.mark.asyncio
async def test_invalid_severity_rejected():
    result = await validate_tag(_base_tag(severity="catastrophic"), SEGMENTS, CALL_DURATION)
    assert result.status == "rejected"
    assert "severity" in result.reason.lower()


@pytest.mark.asyncio
async def test_empty_quote_rejected():
    # The exact failure mode observed live: LLM emitted NO_TRIAL_BOOKING with
    # quote="" during Phase 3 testing against call_03_no_discovery.wav.
    result = await validate_tag(_base_tag(quote="", tag="NO_TRIAL_BOOKING"), SEGMENTS, CALL_DURATION)
    assert result.status == "rejected"
    assert "quote" in result.reason.lower()


@pytest.mark.asyncio
async def test_timestamp_outside_call_duration_rejected():
    result = await validate_tag(_base_tag(start_ts=500.0, end_ts=510.0), SEGMENTS, CALL_DURATION)
    assert result.status == "rejected"


@pytest.mark.asyncio
async def test_paraphrased_quote_passes_via_semantic_layer():
    # Fuzzy match alone fails this (different wording); the semantic layer
    # (Gemini embeddings) should still catch it — this is exactly the case
    # the design doc calls out: "offer expires tomorrow" vs "offer ends
    # tomorrow". Rejected outright would defeat the point of having a
    # semantic layer at all — never silently rejected for paraphrase alone.
    tag = _base_tag(quote="This deal won't be available if you wait")
    result = await validate_tag(tag, SEGMENTS, CALL_DURATION)
    assert result.status in ("open", "needs_review")


@pytest.mark.asyncio
async def test_hallucinated_quote_not_in_transcript_needs_review():
    tag = _base_tag(quote="I will personally guarantee your money back in writing")
    result = await validate_tag(tag, SEGMENTS, CALL_DURATION)
    assert result.status == "needs_review"


@pytest.mark.asyncio
async def test_needs_review_tag_is_valid_not_rejected():
    # needs_review means "schema-valid but low match confidence" — it must
    # still be storable (surfaced for human review), not silently dropped.
    # Bound against the real threshold constant (not a hardcoded number) so
    # this stays correct if SEMANTIC_THRESHOLD is ever recalibrated again.
    tag = _base_tag(quote="Completely unrelated sentence about the weather today")
    result = await validate_tag(tag, SEGMENTS, CALL_DURATION)
    assert result.status == "needs_review"
    assert result.validation_score < SEMANTIC_THRESHOLD
