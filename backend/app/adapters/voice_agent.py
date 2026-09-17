"""Voice agent source adapter: turns a finished routers/voice_agent.py
conversation into a CallEvent, the same internal contract every other
source (file upload, a future telephony webhook) normalizes into. This is
what lets a voice-agent call flow through the *exact* existing pipeline --
PII redaction, issue detection, dimension rating, deterministic scoring --
with zero new scoring infrastructure. See adapters/base.py's own docstring:
this is precisely the extension point it was designed for.

Distinct from FileUploadAdapter in one structural way: the conversation is
already transcribed (services/voice_agent.py's turn-by-turn history) and
the speaker roles are already known (the agent said what it said; the
caller said what they said -- no ambiguous "Speaker 0/1" to resolve). That
known transcript rides along in raw_metadata["pending_segments"];
services/processor.py checks for it and skips both the Deepgram call and
the speaker-ID LLM pass when present.
"""
import uuid
from datetime import datetime, timezone

from app.adapters.base import BaseSourceAdapter, CallEvent
from app.config import settings

# No real per-word timing exists for a voice-agent turn (unlike Deepgram's
# batch transcription, which has it from word-level alignment) -- this is a
# rough spoken-pace estimate so segments get plausible, monotonically
# increasing timestamps. Good enough for services/validation.py's
# window-based evidence matching (which already falls back to a full-
# transcript search if a window comes up empty), not meant to be exact.
_ESTIMATED_WORDS_PER_SECOND = 2.5
_MIN_TURN_SECONDS = 1.0
_GAP_BETWEEN_TURNS_SECONDS = 0.3

_ROLE_MAP = {"agent": "advisor", "caller": "customer"}
_LABEL_MAP = {"agent": "Agent", "caller": "Caller"}


def _build_pending_segments(history: list[dict[str, str]]) -> tuple[list[dict], float]:
    segments: list[dict] = []
    cursor = 0.0
    for turn in history:
        role = turn["role"]
        text = turn["text"]
        word_count = max(1, len(text.split()))
        duration = max(_MIN_TURN_SECONDS, word_count / _ESTIMATED_WORDS_PER_SECOND)
        start_ts, end_ts = cursor, cursor + duration
        segments.append(
            {
                "speaker_label": _LABEL_MAP.get(role, role),
                "speaker_role": _ROLE_MAP.get(role, role),
                "text": text,
                "start_ts": start_ts,
                "end_ts": end_ts,
            }
        )
        cursor = end_ts + _GAP_BETWEEN_TURNS_SECONDS
    return segments, cursor


class VoiceAgentAdapter(BaseSourceAdapter):
    """See routers/voice_agent.py, the only caller -- invoked once, when a
    conversation reaches its closing line (VoiceAgentState.done)."""

    async def normalize(self, raw_payload: dict) -> CallEvent:
        """
        raw_payload keys: history (list[{"role": "agent"|"caller", "text": str}])
        """
        history: list[dict[str, str]] = raw_payload["history"]
        segments, duration_secs = _build_pending_segments(history)

        return CallEvent(
            external_id=str(uuid.uuid4()),
            source_system="voice_agent",
            advisor_id=settings.AI_AGENT_ADVISOR_ID,
            # No single recording exists (see services/tts.py's docstring --
            # this is a deliberate scope decision, not an oversight): the
            # caller's raw mic audio is streamed straight to Deepgram and
            # never saved, and the agent's replies are separate per-turn TTS
            # clips, not one mixed call recording. GET /api/calls/{id}/audio
            # already degrades to a clean 404 for any audio_ref that isn't a
            # real file -- confirmed by reading that route, not assumed.
            audio_ref="voice_agent:no_recording",
            duration_secs=int(duration_secs),
            called_at=datetime.now(timezone.utc),
            raw_metadata={"pending_segments": segments},
        )
