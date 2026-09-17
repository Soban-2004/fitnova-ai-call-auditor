"""Automated voice intake agent WebSocket: raw 16kHz mono PCM audio in
(the caller's mic), a real spoken conversation out. Stage 3 of fitnova's
voice-AI roadmap -- unlike routers/live.py (a silent coaching companion),
this endpoint IS one side of the conversation: it listens, decides what to
say via services/voice_agent.py, and speaks it via services/tts.py
(Cartesia). Same connection-lifecycle-only responsibility split as live.py
-- the turn logic and prompting live in the services layer.

Client protocol:
  in:  binary WebSocket frames of raw linear16 PCM audio (see
       services/live_call.SAMPLE_RATE/ENCODING/CHANNELS -- same format,
       reused so the frontend's mic-capture code needs no changes)
  out: JSON text frames --
       {"type": "transcript", "text": str, "is_final": bool}  -- caller's speech
       {"type": "agent_text", "text": str}                    -- sent right before the matching audio
       {"type": "interrupt"}      -- caller started talking over the agent; stop playback now
       {"type": "speech_started"} / {"type": "utterance_end"} -- caller's VAD state
       {"type": "done", "call_id": str | null} -- agent gave its closing line, conversation over;
                                                   call_id is set once the conversation is persisted
                                                   for scoring (see _persist_conversation), null if
                                                   that failed -- the conversation itself still succeeded
       {"type": "error", "message": str}
       binary WAV audio frames -- the agent's spoken reply (always preceded by its agent_text frame)
"""
import asyncio
import logging

from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.adapters.voice_agent import VoiceAgentAdapter
from app.config import settings
from app.database import async_session_factory
from app.models.lead import Lead
from app.services.ingestion import DuplicateCallError, ingest_call_event
from app.services.live_call import CHANNELS, ENCODING, SAMPLE_RATE
from app.services.tts import synthesize
from app.services.voice_agent import VoiceAgentState, extract_lead_info, generate_reply

logger = logging.getLogger("fitnova.voice_agent_router")
_adapter = VoiceAgentAdapter()

router = APIRouter(prefix="/ws", tags=["voice-agent"])

# scripts/eval_voice_agent.py caught this live: Deepgram's speech_final can
# fire on a brief mid-sentence pause, not just a genuine end-of-turn -- one
# run had the agent completely re-ask its first question because it took a
# turn on a caller sentence that was still incomplete. This debounce absorbs
# that: a turn attempt waits this long before actually generating a reply,
# and any *newer* trigger (more speech arrived) cancels the stale one via
# the epoch check in maybe_take_turn, so only the last, fullest buffer wins.
# 0.4s wasn't enough for a spoken-out phone number specifically -- caught
# live, a run where the caller read digits one at a time produced 6-7
# separate agent replies for what should have been one turn, because the
# gap between digit groups occasionally exceeded the window on its own.
# Widened for headroom; a fully robust fix for numeric/spelled-out input
# would need its own detection, not just a bigger timer -- noted, not
# chased further here.
TURN_DEBOUNCE_SECONDS = 0.7


async def _persist_conversation(state: VoiceAgentState) -> str | None:
    """Turns the finished conversation into a real, scoreable `calls` row,
    AND the AI agent's actual hand-off to a human: a Lead row, not just a
    spoken promise (see app/models/lead.py's docstring). Both are written
    in the same transaction -- a call with no lead, or a lead pointing at
    a call that doesn't exist, would both be worse than persisting
    neither. Never raises: a persistence failure must not take down a
    conversation that already completed successfully from the caller's
    perspective; it's logged and the caller gets call_id=None in the
    "done" message instead.
    """
    try:
        event = await _adapter.normalize({"history": state.history})
        lead_info = await extract_lead_info(state.history)
        async with async_session_factory() as session:
            try:
                result = await ingest_call_event(session, event)
            except DuplicateCallError as e:
                await session.rollback()
                raise e
            session.add(
                Lead(
                    call_id=result.call_id,
                    customer_name=lead_info.get("customer_name"),
                    customer_phone=lead_info.get("customer_phone"),
                    fitness_goal=lead_info.get("fitness_goal"),
                    health_notes=lead_info.get("health_notes"),
                    availability=lead_info.get("availability"),
                    confirmed_time=lead_info.get("confirmed_time"),
                )
            )
            await session.commit()
            return result.call_id
    except Exception as e:
        logger.warning("Failed to persist voice-agent conversation for scoring: %s", e)
        return None


async def _speak_turn(websocket: WebSocket, state: VoiceAgentState, agent_text: str) -> None:
    """Sends one agent turn: the text first (so the transcript UI updates
    immediately), then the synthesized audio if TTS succeeded. A TTS failure
    degrades to text-only -- see services/tts.py -- the conversation keeps
    going either way."""
    state.add_turn("agent", agent_text)
    state.agent_is_speaking = True
    await websocket.send_json({"type": "agent_text", "text": agent_text})
    audio = await synthesize(agent_text)
    if audio:
        await websocket.send_bytes(audio)
    state.agent_is_speaking = False

    if state.done:
        call_id = await _persist_conversation(state)
        await websocket.send_json({"type": "done", "call_id": call_id})


@router.websocket("/agent")
async def voice_agent_call(websocket: WebSocket) -> None:
    await websocket.accept()

    if not settings.DEEPGRAM_API_KEY:
        await websocket.send_json({"type": "error", "message": "DEEPGRAM_API_KEY is not set"})
        await websocket.close()
        return

    state = VoiceAgentState()
    caller_buffer: list[str] = []  # final utterances said since the agent's last turn
    is_generating_reply = False  # re-entrancy guard: consecutive speech_final events can overlap
    turn_epoch = 0  # bumped on every trigger; a stale attempt checks it still matches before acting

    dg_connection = DeepgramClient(settings.DEEPGRAM_API_KEY).listen.asyncwebsocket.v("1")

    async def maybe_take_turn() -> None:
        nonlocal is_generating_reply, turn_epoch
        if not caller_buffer or is_generating_reply or state.done:
            return

        turn_epoch += 1
        my_epoch = turn_epoch
        await asyncio.sleep(TURN_DEBOUNCE_SECONDS)
        if turn_epoch != my_epoch or is_generating_reply or state.done:
            # A newer speech_final/UtteranceEnd fired during the debounce --
            # the caller kept talking, so that trigger owns this turn now
            # (with a fuller caller_buffer) and this stale attempt bows out.
            return

        is_generating_reply = True
        try:
            caller_text = " ".join(caller_buffer)
            caller_buffer.clear()
            state.add_turn("caller", caller_text)
            reply = await generate_reply(state)
            await _speak_turn(websocket, state, reply)
        finally:
            is_generating_reply = False

    async def on_transcript(_, *, result, **kwargs) -> None:
        alt = result.channel.alternatives[0]
        text = (alt.transcript or "").strip()
        if not text:
            return

        await websocket.send_json({"type": "transcript", "text": text, "is_final": result.is_final})

        if result.is_final:
            caller_buffer.append(text)

        if result.speech_final:
            await maybe_take_turn()

    async def on_speech_started(_, **kwargs) -> None:
        await websocket.send_json({"type": "speech_started"})
        if state.agent_is_speaking:
            # Barge-in: the caller started talking while the agent's audio
            # was still playing client-side -- tell the frontend to stop
            # immediately (see components/live/VoiceAgentPanel.tsx). The
            # agent's own turn already finished generating by the time this
            # fires (the whole reply is synthesized before send_bytes), so
            # there's no in-flight generation to cancel server-side, only
            # playback to cut short on the client.
            await websocket.send_json({"type": "interrupt"})

    async def on_utterance_end(_, **kwargs) -> None:
        await websocket.send_json({"type": "utterance_end"})
        await maybe_take_turn()

    async def on_error(_, *, error, **kwargs) -> None:
        logger.warning("Deepgram live error: %s", error)
        try:
            await websocket.send_json({"type": "error", "message": str(error)})
        except Exception:
            pass

    dg_connection.on(LiveTranscriptionEvents.Transcript, on_transcript)
    dg_connection.on(LiveTranscriptionEvents.SpeechStarted, on_speech_started)
    dg_connection.on(LiveTranscriptionEvents.UtteranceEnd, on_utterance_end)
    dg_connection.on(LiveTranscriptionEvents.Error, on_error)

    options = LiveOptions(
        model="nova-3",
        language="multi",
        encoding=ENCODING,
        sample_rate=SAMPLE_RATE,
        channels=CHANNELS,
        smart_format=True,
        punctuate=True,
        interim_results=True,
        utterance_end_ms="1000",
        vad_events=True,
        # Root cause of a real bug caught live (scripts/eval_voice_agent.py):
        # left at Deepgram's default, speech_final fired on just "Hi." --
        # 3.5s of real audio before the rest of one continuous sentence even
        # arrived -- a natural breath-pause was mistaken for the caller being
        # done, so the agent replied (re-asking its own question) before the
        # caller finished talking. endpointing is the actual lever for this
        # (how much silence speech_final requires), not utterance_end_ms
        # (that governs the separate, coarser UtteranceEnd event) or the
        # client-side debounce below (a shorter default than this makes any
        # client debounce moot -- it fires long before a few hundred ms of
        # buffering could ever catch it).
        endpointing=300,
    )

    started = await dg_connection.start(options)
    if not started:
        await websocket.send_json({"type": "error", "message": "Could not start Deepgram live connection"})
        await websocket.close()
        return

    # The agent opens the conversation -- greet before waiting on the caller,
    # exactly like a real intake call. generate_reply with empty history
    # produces the greeting (see services/voice_agent.py's system prompt).
    greeting = await generate_reply(state)
    await _speak_turn(websocket, state, greeting)

    try:
        while True:
            audio_chunk = await websocket.receive_bytes()
            await dg_connection.send(audio_chunk)
    except WebSocketDisconnect:
        pass
    finally:
        await dg_connection.finish()
