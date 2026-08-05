"""Deepgram Nova-3 integration: one API call handles both STT and speaker
diarization. Returns per-utterance segments with speaker labels and
word-level-derived timestamps.

Edge cases handled here:
- Mono / single-speaker audio: Deepgram still returns utterances but only
  ever emits "Speaker 0" — processor.py detects this after the fact and
  flags diarization_quality='mono' on the call.
- API failure: raised as TranscriptionError, caught by the state machine
  in processor.py which marks the call FAILED for retry.
"""
from dataclasses import dataclass

from deepgram import DeepgramClient, PrerecordedOptions

from app.config import settings


class TranscriptionError(Exception):
    """Raised when Deepgram fails or returns an unusable response."""
    pass


@dataclass
class TranscriptResult:
    segments: list[dict]
    duration_secs: float
    distinct_speakers: int


def _client() -> DeepgramClient:
    if not settings.DEEPGRAM_API_KEY:
        raise TranscriptionError("DEEPGRAM_API_KEY is not set")
    return DeepgramClient(settings.DEEPGRAM_API_KEY)


async def transcribe_call(audio_path: str, language: str | None = "multi") -> TranscriptResult:
    """Transcribe + diarize an audio file.

    `language="multi"` is Deepgram's actual multilingual code-switching mode
    (confirmed against Deepgram's docs — NOT language="hi", which forces the
    monolingual Hindi model and was observed transliterating pure-English
    audio into Devanagari script during testing, e.g. "Priya" -> "प्रिया".
    That would also silently break the Latin-script PII name-redaction regex
    in pii_redaction.py). "multi" covers Hindi-English code-switching plus
    9 other languages without that failure mode. Pass a specific code (e.g.
    "en") to pin a single language, or None to auto-detect.
    """
    try:
        with open(audio_path, "rb") as f:
            buffer_data = f.read()
    except OSError as e:
        raise TranscriptionError(f"Could not read audio file {audio_path}: {e}") from e

    options = PrerecordedOptions(
        model="nova-3",
        diarize=True,
        utterances=True,
        smart_format=True,
        punctuate=True,
        language=language,
    )

    try:
        client = _client()
        # asyncrest (not rest) so the blocking HTTP call doesn't stall the
        # event loop — the background worker in processor.py awaits this.
        response = await client.listen.asyncrest.v("1").transcribe_file(
            {"buffer": buffer_data},
            options,
        )
    except Exception as e:
        raise TranscriptionError(f"Deepgram API error: {e}") from e

    return _parse_response(response)


def _parse_response(response) -> TranscriptResult:
    try:
        result = response.results
        metadata = response.metadata
        duration = float(metadata.duration) if metadata and metadata.duration else 0.0

        utterances = getattr(result, "utterances", None) or []
        segments: list[dict] = []
        speakers: set[int] = set()

        for utt in utterances:
            speaker_idx = getattr(utt, "speaker", 0) or 0
            speakers.add(speaker_idx)
            segments.append(
                {
                    "speaker_label": f"Speaker {speaker_idx}",
                    "speaker_role": None,  # set later by the speaker-ID LLM pass
                    "text": (utt.transcript or "").strip(),
                    "start_ts": float(utt.start),
                    "end_ts": float(utt.end),
                }
            )

        if not segments:
            # Fall back to the flat channel transcript if utterances came back
            # empty (can happen on very short / silent clips).
            alt = result.channels[0].alternatives[0]
            text = (alt.transcript or "").strip()
            if text:
                segments.append(
                    {
                        "speaker_label": "Speaker 0",
                        "speaker_role": None,
                        "text": text,
                        "start_ts": 0.0,
                        "end_ts": duration,
                    }
                )
            speakers.add(0)

        return TranscriptResult(
            segments=segments,
            duration_secs=duration,
            distinct_speakers=len(speakers) if segments else 0,
        )
    except (AttributeError, IndexError, KeyError) as e:
        raise TranscriptionError(f"Unexpected Deepgram response shape: {e}") from e
