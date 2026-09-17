"""Live-call WebSocket: raw 16kHz mono PCM audio in, real-time transcript +
coaching-nudge events out. See services/live_call.py for the sliding-window
nudge logic this router wires up to a real Deepgram streaming connection --
this file owns only the connection lifecycle (accept, relay audio in,
relay events out, clean up), same separation of concerns as processor.py
(orchestration) vs services/analysis.py (LLM logic) elsewhere in this app.

Requires ?advisor_id=<uuid> on the connect URL -- tying a session to a real
advisor is what lets it persist as a real, scored `calls` row when it ends
(adapters/live_call.py), instead of being an anonymous demo nobody's
dashboard ever sees. Rejected (close before accept-time work) if the
advisor doesn't exist.

Client protocol:
  in:  binary WebSocket frames of raw linear16 PCM audio (see
       services/live_call.SAMPLE_RATE/ENCODING/CHANNELS)
  out: JSON text frames --
       {"type": "transcript", "text": str, "is_final": bool}
       {"type": "nudge", "text": str}
       {"type": "speech_started"}   -- Deepgram's VAD detected someone talking
       {"type": "utterance_end"}    -- Deepgram detected a genuine pause (turn boundary)
       {"type": "error", "message": str}
"""
import logging

from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.adapters.live_call import LiveCallAdapter
from app.config import settings
from app.database import async_session_factory
from app.models.org import Advisor
from app.services.ingestion import DuplicateCallError, ingest_call_event
from app.services.live_call import CHANNELS, ENCODING, SAMPLE_RATE, LiveCallState, maybe_generate_nudge

logger = logging.getLogger("fitnova.live")

router = APIRouter(prefix="/ws", tags=["live"])
_adapter = LiveCallAdapter()

# A one- or two-utterance blip (someone clicking Start then immediately
# Stop) isn't a real coaching session -- not worth polluting an advisor's
# call history with. A genuine exchange clears this easily.
_MIN_SEGMENTS_TO_PERSIST = 4


def _majority_speaker(words: list) -> str:
    """Deepgram's live diarization reports a speaker per *word*, not per
    utterance (unlike the batch API's utterances=True) -- a transcript
    segment can in principle span a fast handoff. Majority vote across the
    segment's words is the standard, simple resolution; ties break toward
    the first word's speaker (whoever started the segment)."""
    speakers = [w.speaker for w in words if w.speaker is not None]
    if not speakers:
        return "Speaker 0"
    counts: dict[int, int] = {}
    for s in speakers:
        counts[s] = counts.get(s, 0) + 1
    winner = max(counts.items(), key=lambda kv: (kv[1], -speakers.index(kv[0])))[0]
    return f"Speaker {winner}"


async def _persist_session(advisor_id: str, state: LiveCallState) -> str | None:
    """Turns a finished live-coaching session into a real, scored `calls`
    row -- see adapters/live_call.py's module docstring. Never raises: a
    persistence failure must not be visible to an advisor whose call
    already happened successfully; it's logged and swallowed.
    """
    if len(state.segments) < _MIN_SEGMENTS_TO_PERSIST:
        logger.info("Live session too short to persist (%d segment(s)), skipping", len(state.segments))
        return None
    try:
        event = await _adapter.normalize({"advisor_id": advisor_id, "segments": state.segments})
        async with async_session_factory() as session:
            try:
                result = await ingest_call_event(session, event)
            except DuplicateCallError as e:
                await session.rollback()
                raise e
            await session.commit()
            return result.call_id
    except Exception as e:
        logger.warning("Failed to persist live-coaching session for scoring: %s", e)
        return None


@router.websocket("/live")
async def live_call(websocket: WebSocket) -> None:
    advisor_id = websocket.query_params.get("advisor_id")
    await websocket.accept()

    if not advisor_id:
        await websocket.send_json({"type": "error", "message": "advisor_id is required"})
        await websocket.close()
        return

    async with async_session_factory() as session:
        advisor = await session.get(Advisor, advisor_id)
    if advisor is None:
        await websocket.send_json({"type": "error", "message": f"Advisor {advisor_id} not found"})
        await websocket.close()
        return

    if not settings.DEEPGRAM_API_KEY:
        await websocket.send_json({"type": "error", "message": "DEEPGRAM_API_KEY is not set"})
        await websocket.close()
        return

    state = LiveCallState()
    dg_connection = DeepgramClient(settings.DEEPGRAM_API_KEY).listen.asyncwebsocket.v("1")

    async def on_transcript(_, *, result, **kwargs) -> None:
        alt = result.channel.alternatives[0]
        text = (alt.transcript or "").strip()
        if not text:
            return  # Deepgram emits empty interim results during silence -- nothing to relay

        await websocket.send_json({"type": "transcript", "text": text, "is_final": result.is_final})

        if result.is_final:
            state.add_final_utterance(text)
            state.add_final_segment(_majority_speaker(alt.words), text, result.start, result.start + result.duration)

        # result.speech_final -- distinct from is_final -- is Deepgram's own
        # per-utterance endpointing signal ("voice activity detected a pause
        # here"), on every Transcript event with no extra wait. UtteranceEnd
        # (below) needs ~1s of continuous silence and is a useful backstop,
        # but relying on it alone leaves is_speaking stuck True for the rest
        # of the call whenever real speech never has a gap that long (a
        # regression caught live: streaming one continuous TTS-narrated
        # scenario clip never produced a single UtteranceEnd, silently
        # blocking every nudge for the whole call).
        if result.speech_final:
            state.is_speaking = False
            nudge = await maybe_generate_nudge(state)
            if nudge:
                await websocket.send_json({"type": "nudge", "text": nudge})

    async def on_speech_started(_, **kwargs) -> None:
        state.is_speaking = True
        await websocket.send_json({"type": "speech_started"})

    async def on_utterance_end(_, **kwargs) -> None:
        # Deepgram's dedicated "the speaker genuinely paused" signal --
        # distinct from a per-segment is_final transcript event, which can
        # fire mid-utterance for a long turn. This is the real turn boundary,
        # and a second (more reliable) trigger for checking a nudge, on top
        # of the one already in on_transcript above.
        state.is_speaking = False
        await websocket.send_json({"type": "utterance_end"})
        nudge = await maybe_generate_nudge(state)
        if nudge:
            await websocket.send_json({"type": "nudge", "text": nudge})

    async def on_error(_, *, error, **kwargs) -> None:
        logger.warning("Deepgram live error: %s", error)
        try:
            await websocket.send_json({"type": "error", "message": str(error)})
        except Exception:
            pass  # client socket may already be gone -- nothing more to do

    dg_connection.on(LiveTranscriptionEvents.Transcript, on_transcript)
    dg_connection.on(LiveTranscriptionEvents.SpeechStarted, on_speech_started)
    dg_connection.on(LiveTranscriptionEvents.UtteranceEnd, on_utterance_end)
    dg_connection.on(LiveTranscriptionEvents.Error, on_error)

    options = LiveOptions(
        model="nova-3",
        language="multi",  # same rationale as services/transcription.py's batch path
        encoding=ENCODING,
        sample_rate=SAMPLE_RATE,
        channels=CHANNELS,
        smart_format=True,
        punctuate=True,
        interim_results=True,
        utterance_end_ms="1000",
        vad_events=True,
        # Needed for persistence (_persist_session/adapters/live_call.py):
        # without this, every word comes back speaker=None and every
        # segment would collapse onto one label. Not needed for the
        # nudge-coaching logic itself, which stays role-agnostic on purpose
        # (see services/live_call.py's module docstring).
        diarize=True,
        # Deepgram's default endpointing fires speech_final on a short
        # breath-pause mid-sentence, not just a genuine turn end -- caught
        # live in routers/voice_agent.py (same LiveOptions shape), where it
        # made the agent respond before the caller finished talking. Applied
        # here too since the nudge-check trigger has the identical risk,
        # just a quieter failure mode (an early nudge check on a half-said
        # sentence) than the agent's (a wrong turn).
        endpointing=300,
    )

    started = await dg_connection.start(options)
    if not started:
        await websocket.send_json({"type": "error", "message": "Could not start Deepgram live connection"})
        await websocket.close()
        return

    try:
        while True:
            audio_chunk = await websocket.receive_bytes()
            await dg_connection.send(audio_chunk)
    except WebSocketDisconnect:
        pass
    finally:
        await dg_connection.finish()
        call_id = await _persist_session(advisor_id, state)
        logger.info(
            "Live session ended for advisor %s: %d segment(s), persisted as %s",
            advisor_id, len(state.segments), call_id or "(not persisted)",
        )
