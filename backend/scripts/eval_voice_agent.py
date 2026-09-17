"""Simulation-based evaluation for the voice intake agent (routers/
voice_agent.py) -- Stage 3's equivalent of eval_live_call.py.

Drives a full, real, multi-turn spoken conversation against the real
WebSocket endpoint: a scripted synthetic "caller" answers the agent's
questions in order, each answer synthesized once via edge-tts and streamed
in real time, exactly like a real caller's mic audio would arrive. Measures
whether the agent actually asks its three required questions in order,
whether it produces real spoken audio for each turn, how long each turn
takes, and whether it reaches its closing line -- not "is the phrasing
good" (that's a judgment call for a human listening to the recordings this
script saves), but "does the real-time conversational loop behave
correctly."

Requires the backend already running -- same reasoning as
eval_live_call.py: this drives the real ASGI/WebSocket stack, real Deepgram
streaming, real LLM calls, and real Cartesia TTS calls end to end, not an
in-process fake. Also saves each agent turn's audio to
scripts/_eval_audio_cache/voice_agent_turn_N.wav so you can actually listen
to what it said.

Usage:
    # Terminal 1, from backend/:
    uvicorn app.main:app --host 127.0.0.1 --port 8000

    # Terminal 2, from backend/:
    python scripts/eval_voice_agent.py [--host 127.0.0.1] [--port 8000]
"""
import argparse
import asyncio
import hashlib
import io
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import edge_tts
import requests
import websockets
from pydub import AudioSegment

# Caught live: spoken agent replies occasionally include characters (curly
# quotes, non-breaking hyphens) that don't exist in Windows' default console
# codepage -- printing one crashed the whole run *after* the conversation
# had already completed correctly server-side. This is a display problem,
# not a data problem; UTF-8 with replacement keeps the script from dying on
# a character it can't render.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_SCRIPT_DIR = Path(__file__).resolve().parent
_AUDIO_CACHE_DIR = _SCRIPT_DIR / "_eval_audio_cache"
_RESULTS_PATH = _SCRIPT_DIR / "eval_results_voice_agent.json"
_MAX_HISTORY_ENTRIES = 50

SAMPLE_RATE = 16000
CHUNK_MS = 100
CALLER_VOICE = "en-US-AriaNeural"

# Fixed caller answers, in the order the agent's system prompt asks for them
# (goal -> injuries -> availability) -- see services/voice_agent.py's
# _AGENT_SYSTEM_PROMPT. Loosely realistic, not word-perfect to any expected
# transcript, since the point is exercising the real turn-taking loop.
_CALLER_ANSWERS = [
    # services/voice_agent.py's prompt now asks for name and a callback
    # number first (as two separate single-fact questions -- a compound
    # "name and number" question was caught live getting the agent stuck
    # re-asking it forever, never progressing), needed for the resulting
    # Lead (app/models/lead.py) to actually be contactable.
    "This is Karan Verma.",
    "You can reach me at nine eight seven six five four three two one zero.",
    "I am mainly looking to lose some weight and build a bit of strength.",
    "No injuries, I am generally pretty healthy.",
    "Weekday evenings work best for me, after six PM.",
    # Generic on purpose -- doesn't name a specific day/time since the agent
    # picks those itself (see services/voice_agent.py's updated prompt:
    # propose two concrete slots and get one confirmed, instead of just
    # promising a follow-up). "The first one" works regardless of which two
    # times it actually proposes.
    "The first one works great for me, thank you.",
]


@dataclass
class TurnResult:
    index: int
    agent_text: str = ""
    audio_bytes: int = 0
    time_to_agent_text_ms: float | None = None
    time_to_agent_audio_ms: float | None = None


@dataclass
class ConversationResult:
    turns: list[TurnResult] = field(default_factory=list)
    reached_done: bool = False
    call_id: str | None = None  # set once the conversation is persisted for scoring, see routers/voice_agent.py
    interrupts_seen: int = 0
    errors: list[str] = field(default_factory=list)
    total_seconds: float = 0.0


async def _synthesize_pcm(text: str, cache_name: str) -> bytes:
    """Caught live: this used to cache by a caller-supplied positional label
    (f"voice_agent_caller_answer_{i}") -- editing _CALLER_ANSWERS' wording or
    length left stale audio sitting under the same filename, silently
    playing OLD text while the script printed the NEW text. The agent's
    turn-taking was never actually broken; it was correctly reacting to
    audio that didn't match what anyone reading the log would assume it
    heard. Hashing the real text into the key makes any content change
    self-invalidating -- no positional index to go stale."""
    _AUDIO_CACHE_DIR.mkdir(exist_ok=True)
    digest = hashlib.sha1(f"{CALLER_VOICE}:{text}".encode()).hexdigest()[:12]
    cache_path = _AUDIO_CACHE_DIR / f"{cache_name}_{digest}.pcm"
    if cache_path.exists():
        return cache_path.read_bytes()

    communicate = edge_tts.Communicate(text, CALLER_VOICE)
    buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    buf.seek(0)
    audio = AudioSegment.from_file(buf, format="mp3")
    audio = audio.set_frame_rate(SAMPLE_RATE).set_channels(1).set_sample_width(2)
    pcm = audio.raw_data
    cache_path.write_bytes(pcm)
    return pcm


async def _stream_pcm(ws: websockets.WebSocketClientProtocol, pcm: bytes) -> None:
    bytes_per_chunk = int(SAMPLE_RATE * 2 * (CHUNK_MS / 1000))
    for i in range(0, len(pcm), bytes_per_chunk):
        await ws.send(pcm[i : i + bytes_per_chunk])
        await asyncio.sleep(CHUNK_MS / 1000)


_KEEPALIVE_SILENCE_CHUNK = b"\x00\x00" * int(SAMPLE_RATE * (CHUNK_MS / 1000))  # 100ms of 16-bit silence
_KEEPALIVE_INTERVAL_SECONDS = 3.0


async def _keepalive(ws) -> None:
    """A real browser mic keeps streaming (silence included) the whole time
    a caller is listening for a reply; this script only sends audio in
    bursts (see _stream_pcm), leaving real gaps while waiting for the
    agent's LLM+TTS turn. Caught live: those gaps occasionally exceeded
    Deepgram's own idle-connection timeout (~10s, no audio/text received --
    same limit documented in services/live_call.py's history), silently
    killing the whole test partway through. This runs for the life of the
    connection and pads the idle gaps with real silence frames, the same
    thing continuous mic capture would provide for free.
    """
    try:
        while True:
            await asyncio.sleep(_KEEPALIVE_INTERVAL_SECONDS)
            await ws.send(_KEEPALIVE_SILENCE_CHUNK)
    except asyncio.CancelledError:
        pass
    except websockets.exceptions.ConnectionClosed:
        pass


async def run_conversation(ws_url: str) -> ConversationResult:
    result = ConversationResult()
    start_time = time.monotonic()
    turn_index = -1  # -1 = the agent's opening greeting, before any caller answer

    async with websockets.connect(ws_url, max_size=None) as ws:
        keepalive_task = asyncio.create_task(_keepalive(ws))
        current_turn: TurnResult | None = None

        async def receive_until(predicate) -> None:
            """Pumps incoming events, updating `current_turn`/result state,
            until `predicate()` returns True (e.g. this turn's audio arrived,
            or the conversation ended)."""
            nonlocal current_turn
            while not predicate():
                message = await asyncio.wait_for(ws.recv(), timeout=30)
                elapsed_ms = (time.monotonic() - start_time) * 1000
                if isinstance(message, bytes):
                    if current_turn is not None:
                        current_turn.audio_bytes = len(message)
                        if current_turn.time_to_agent_audio_ms is None:
                            current_turn.time_to_agent_audio_ms = elapsed_ms
                        turn_path = _AUDIO_CACHE_DIR / f"voice_agent_turn_{current_turn.index}.wav"
                        turn_path.write_bytes(message)
                    continue
                data = json.loads(message)
                if data["type"] == "agent_text":
                    if current_turn is not None:
                        current_turn.agent_text = data["text"]
                        if current_turn.time_to_agent_text_ms is None:
                            current_turn.time_to_agent_text_ms = elapsed_ms
                elif data["type"] == "interrupt":
                    result.interrupts_seen += 1
                elif data["type"] == "done":
                    result.reached_done = True
                    result.call_id = data.get("call_id")
                elif data["type"] == "error":
                    result.errors.append(data["message"])

        try:
            # Turn -1: wait for the agent's opening greeting (text + audio)
            # before the caller says anything -- this is the behavior that
            # actually proves the agent opens the conversation rather than
            # waiting mute.
            current_turn = TurnResult(index=0)
            result.turns.append(current_turn)
            await receive_until(lambda: current_turn.agent_text and current_turn.audio_bytes)
            print(f"[agent, greeting] {current_turn.agent_text!r} ({current_turn.audio_bytes}B audio)")

            for i, answer in enumerate(_CALLER_ANSWERS, start=1):
                if result.reached_done:
                    break
                pcm = await _synthesize_pcm(answer, f"voice_agent_caller_answer_{i}")
                print(f"[caller] {answer!r}")
                await _stream_pcm(ws, pcm)

                current_turn = TurnResult(index=i)
                result.turns.append(current_turn)
                await receive_until(
                    lambda: (current_turn.agent_text and current_turn.audio_bytes) or result.reached_done
                )
                if current_turn.agent_text:
                    print(f"[agent, turn {i}] {current_turn.agent_text!r} ({current_turn.audio_bytes}B audio)")

            # Drain any trailing "done" that arrives after the last audio frame.
            if not result.reached_done:
                try:
                    await asyncio.wait_for(receive_until(lambda: result.reached_done), timeout=5)
                except asyncio.TimeoutError:
                    pass
        finally:
            keepalive_task.cancel()

    result.total_seconds = time.monotonic() - start_time
    return result


def _preflight(host: str, port: int) -> None:
    try:
        resp = requests.get(f"http://{host}:{port}/api/health", timeout=3)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(
            f"Backend not reachable at http://{host}:{port} ({e}).\n"
            f"Start it first: uvicorn app.main:app --host {host} --port {port}",
            file=sys.stderr,
        )
        raise SystemExit(1)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    _preflight(args.host, args.port)
    ws_url = f"ws://{args.host}:{args.port}/ws/agent"

    result = await run_conversation(ws_url)

    print("\n=== Overall ===")
    print(f"  turns completed        : {len(result.turns)}")
    print(f"  reached closing line   : {result.reached_done}")
    print(f"  persisted as call_id   : {result.call_id or '(not persisted)'}")
    print(f"  turns with audio       : {sum(1 for t in result.turns if t.audio_bytes > 0)}/{len(result.turns)}")
    print(f"  barge-in interrupts    : {result.interrupts_seen}")
    print(f"  total conversation time: {result.total_seconds:.1f}s")
    print(f"  errors                 : {result.errors}")
    for t in result.turns:
        print(
            f"    turn {t.index}: text@{_fmt_ms(t.time_to_agent_text_ms)} "
            f"audio@{_fmt_ms(t.time_to_agent_audio_ms)} ({t.audio_bytes}B)"
        )

    _append_history(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "turns_completed": len(result.turns),
            "reached_done": result.reached_done,
            "call_id": result.call_id,
            "turns_with_audio": sum(1 for t in result.turns if t.audio_bytes > 0),
            "interrupts_seen": result.interrupts_seen,
            "total_seconds": round(result.total_seconds, 1),
            "errors": result.errors,
            "turns": [
                {
                    "index": t.index,
                    "agent_text": t.agent_text,
                    "audio_bytes": t.audio_bytes,
                    "time_to_agent_text_ms": t.time_to_agent_text_ms,
                    "time_to_agent_audio_ms": t.time_to_agent_audio_ms,
                }
                for t in result.turns
            ],
        }
    )

    all_turns_had_audio = all(t.audio_bytes > 0 for t in result.turns)
    return 0 if result.reached_done and all_turns_had_audio and not result.errors else 1


def _fmt_ms(value: float | None) -> str:
    return f"{value:.0f}ms" if value is not None else "never"


def _append_history(entry: dict) -> None:
    history: list[dict] = []
    if _RESULTS_PATH.exists():
        try:
            history = json.loads(_RESULTS_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            history = []
    history.append(entry)
    history = history[-_MAX_HISTORY_ENTRIES:]
    _RESULTS_PATH.write_text(json.dumps(history, indent=2), encoding="utf-8")
    print(f"\n  (appended to {_RESULTS_PATH.name}, {len(history)} run(s) of history)")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
