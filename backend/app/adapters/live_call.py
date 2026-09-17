"""Live-coaching source adapter: turns a finished routers/live.py session
into a CallEvent, the same internal contract every other source normalizes
into (see adapters/base.py). This is what makes a live-coached call show
up in the advisor's own Recent Calls and get scored by the exact same
pipeline as an uploaded recording -- the whole point of tying Live Call
Coaching to a real advisor identity instead of leaving it an anonymous demo.

Distinct from adapters/voice_agent.py in the one way that actually matters:
a live session is a real human conversation picked up on one mic, diarized
by Deepgram same as any other 2-speaker call -- "Speaker 0"/"Speaker 1" are
known, but *who* is the advisor and who is the customer is not (there's no
scripted turn structure to read it off of, unlike the voice agent). So
these segments carry speaker_label only, no speaker_role -- the normal
speaker-ID LLM pass in processor.py resolves that, exactly as it would for
an uploaded recording. See processor.py's speaker_roles_known check, which
is what actually decides whether that pass runs.
"""
import uuid
from datetime import datetime, timezone

from app.adapters.base import BaseSourceAdapter, CallEvent


class LiveCallAdapter(BaseSourceAdapter):
    """See routers/live.py, the only caller -- invoked once, when the
    advisor's session ends, provided enough of a real exchange happened."""

    async def normalize(self, raw_payload: dict) -> CallEvent:
        """
        raw_payload keys: advisor_id (str), segments (list[{"speaker_label",
        "text", "start_ts", "end_ts"}], from LiveCallState.segments)
        """
        advisor_id: str = raw_payload["advisor_id"]
        segments: list[dict] = raw_payload["segments"]
        duration_secs = segments[-1]["end_ts"] if segments else 0.0

        return CallEvent(
            external_id=str(uuid.uuid4()),
            source_system="live_call",
            advisor_id=advisor_id,
            # No single recording exists here either -- same deliberate
            # scope decision as adapters/voice_agent.py, same clean 404 from
            # GET /api/calls/{id}/audio for a sentinel audio_ref.
            audio_ref="live_call:no_recording",
            duration_secs=int(duration_secs),
            called_at=datetime.now(timezone.utc),
            raw_metadata={"pending_segments": segments},
        )
