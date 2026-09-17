"""Simulation-based evaluation for the live-call voice pipeline
(routers/live.py + services/live_call.py) -- Stage 5 of moving fitnova
toward genuine voice-AI engineering practice, not just a working demo.

This measures something different from scripts/eval_issue_detection.py:
that script asks "is the model's judgment correct" (does it flag the right
issues); this one asks "does the real-time pipeline behave correctly and
fast enough under realistic timing" -- time to first transcript, time to
first nudge, whether it actually captured what was said, whether anything
errored. That's the same split the industry's voice-agent simulation
tools (Coval, Cekura) draw between correctness eval and latency/reliability
simulation -- see the research behind this project's staged voice-AI
roadmap.

Deliberately drives the REAL WebSocket endpoint over a real network
connection (not an in-process test double) -- the whole point is testing
the actual ASGI/WebSocket stack, real Deepgram streaming, real LLM calls,
end to end. Requires the backend already running (see USAGE below); this
script does not manage the server's lifecycle itself.

Cost note: each scenario is one real Deepgram streaming connection plus a
handful of real LLM calls -- same quota-consciousness as every other eval
script in this project. Run by hand, not in a request path or a tight loop.

Usage:
    # Terminal 1, from backend/:
    uvicorn app.main:app --host 127.0.0.1 --port 8000

    # Terminal 2, from backend/:
    python scripts/eval_live_call.py [--host 127.0.0.1] [--port 8000]
"""
import argparse
import asyncio
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

# See eval_voice_agent.py's identical fix for why -- spoken transcript text
# can include characters outside Windows' default console codepage.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_SCRIPT_DIR = Path(__file__).resolve().parent
_AUDIO_CACHE_DIR = _SCRIPT_DIR / "_eval_audio_cache"
_RESULTS_PATH = _SCRIPT_DIR / "eval_results_live.json"
_MAX_HISTORY_ENTRIES = 50

SAMPLE_RATE = 16000  # must match backend/app/services/live_call.py exactly
CHUNK_MS = 100  # simulated real-time mic pacing, matches the frontend's rough chunk cadence


@dataclass
class Scenario:
    name: str
    voice: str
    text: str
    # Substrings (lowercased) expected somewhere in the concatenated final
    # transcript -- picked to be robust to Deepgram's smart_format number
    # rendering (e.g. "4,500" vs "four thousand five hundred"), so only
    # non-numeric distinctive phrases are used here.
    expected_keywords: list[str]


_SCENARIOS = [
    Scenario(
        name="good_call",
        voice="en-IN-NeerjaNeural",
        text=(
            "Hi, this is Priya from FitNova. Am I speaking with Karan? "
            "Great! What are you currently looking to work on, weight loss, strength, or general fitness? "
            "Mostly general fitness, I sit at a desk all day and want to get more active. "
            "Makes sense. Any injuries or health conditions I should know about? "
            "No, nothing like that, I am generally healthy. "
            "Good to know. Our Standard plan is four thousand five hundred a month, "
            "three sessions a week plus a diet plan."
        ),
        expected_keywords=["priya", "fitnova", "karan", "weight loss", "desk", "injuries", "healthy"],
    ),
    Scenario(
        name="pressure_call",
        voice="en-IN-PrabhatNeural",
        text=(
            "Hi, this is Rahul from FitNova calling about your fitness enquiry. "
            "Look, I will be direct, we have an offer that expires tonight at midnight, "
            "so I do not want you to miss it. "
            "Normally six thousand a month, but if you lock in right now I can get you a lower rate. "
            "This price is gone the moment I hang up. "
            "Honestly there is only one slot left this month, and thinking it over means losing it."
        ),
        expected_keywords=["rahul", "fitnova", "expires", "midnight", "lock", "slot"],
    ),
]


@dataclass
class ScenarioResult:
    name: str
    audio_seconds: float
    time_to_first_interim_ms: float | None = None
    time_to_first_final_ms: float | None = None
    final_transcript: str = ""
    keywords_found: list[str] = field(default_factory=list)
    keywords_missed: list[str] = field(default_factory=list)
    nudge_count: int = 0
    time_to_first_nudge_ms: float | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def keyword_coverage(self) -> float:
        total = len(self.keywords_found) + len(self.keywords_missed)
        return len(self.keywords_found) / total if total else 1.0


async def _synthesize_pcm(scenario: Scenario) -> bytes:
    """Generates (or reuses a cached copy of) 16kHz mono linear16 PCM for a
    scenario -- same edge-tts -> pydub pipeline already proven for this
    project's other synthetic-audio scripts."""
    _AUDIO_CACHE_DIR.mkdir(exist_ok=True)
    cache_path = _AUDIO_CACHE_DIR / f"{scenario.name}.pcm"
    if cache_path.exists():
        return cache_path.read_bytes()

    communicate = edge_tts.Communicate(scenario.text, scenario.voice)
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


async def _run_scenario(ws_url: str, scenario: Scenario, pcm: bytes) -> tuple[ScenarioResult, list[str]]:
    bytes_per_chunk = int(SAMPLE_RATE * 2 * (CHUNK_MS / 1000))  # 2 bytes/sample (16-bit)
    result = ScenarioResult(name=scenario.name, audio_seconds=len(pcm) / (SAMPLE_RATE * 2))
    start_time = time.monotonic()
    final_chunks: list[str] = []
    nudge_texts: list[str] = []

    async with websockets.connect(ws_url, max_size=None) as ws:

        async def sender():
            for i in range(0, len(pcm), bytes_per_chunk):
                await ws.send(pcm[i : i + bytes_per_chunk])
                await asyncio.sleep(CHUNK_MS / 1000)

        async def receiver():
            async for message in ws:
                elapsed_ms = (time.monotonic() - start_time) * 1000
                data = json.loads(message)
                if data["type"] == "transcript":
                    if result.time_to_first_interim_ms is None:
                        result.time_to_first_interim_ms = elapsed_ms
                    if data["is_final"]:
                        if result.time_to_first_final_ms is None:
                            result.time_to_first_final_ms = elapsed_ms
                        final_chunks.append(data["text"])
                elif data["type"] == "nudge":
                    if result.time_to_first_nudge_ms is None:
                        result.time_to_first_nudge_ms = elapsed_ms
                    result.nudge_count += 1
                    nudge_texts.append(data["text"])
                elif data["type"] == "error":
                    result.errors.append(data["message"])

        recv_task = asyncio.create_task(receiver())
        await sender()
        await ws.close()
        try:
            await asyncio.wait_for(recv_task, timeout=5)
        except asyncio.TimeoutError:
            recv_task.cancel()

    result.final_transcript = " ".join(final_chunks)
    transcript_lower = result.final_transcript.lower()
    for kw in scenario.expected_keywords:
        (result.keywords_found if kw in transcript_lower else result.keywords_missed).append(kw)

    return result, nudge_texts


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
    # A seeded advisor id (Priya Sharma, scripts/seed_db.py's fixed ID) --
    # /ws/live now requires a real advisor_id to connect at all, since a
    # session persists as that advisor's own scored call.
    advisor_id = "c0000000-0000-0000-0000-000000000001"
    ws_url = f"ws://{args.host}:{args.port}/ws/live?advisor_id={advisor_id}"

    results: list[ScenarioResult] = []
    all_nudges: dict[str, list[str]] = {}
    for scenario in _SCENARIOS:
        print(f"\n=== {scenario.name} ===")
        pcm = await _synthesize_pcm(scenario)
        result, nudges = await _run_scenario(ws_url, scenario, pcm)
        results.append(result)
        all_nudges[scenario.name] = nudges

        print(f"  audio duration        : {result.audio_seconds:.1f}s")
        print(f"  time to first interim  : {_fmt_ms(result.time_to_first_interim_ms)}")
        print(f"  time to first final    : {_fmt_ms(result.time_to_first_final_ms)}")
        print(f"  keyword coverage       : {result.keyword_coverage:.0%} ({result.keywords_found})")
        if result.keywords_missed:
            print(f"  MISSED KEYWORDS        : {result.keywords_missed}")
        print(f"  nudges fired           : {result.nudge_count}")
        print(f"  time to first nudge    : {_fmt_ms(result.time_to_first_nudge_ms)}")
        for text in nudges:
            print(f"    -> {text!r}")
        if result.errors:
            print(f"  ERRORS                 : {result.errors}")

    avg_coverage = sum(r.keyword_coverage for r in results) / len(results)
    total_errors = sum(len(r.errors) for r in results)
    finals_seen = [r.time_to_first_final_ms for r in results if r.time_to_first_final_ms is not None]

    print("\n=== Overall ===")
    print(f"  scenarios              : {len(results)}")
    print(f"  avg keyword coverage   : {avg_coverage:.0%}")
    print(f"  scenarios w/ >=1 nudge : {sum(1 for r in results if r.nudge_count > 0)}/{len(results)}")
    print(f"  total errors           : {total_errors}")
    if finals_seen:
        print(f"  avg time to first final: {sum(finals_seen) / len(finals_seen):.0f}ms")

    _append_history(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scenarios": [
                {
                    "name": r.name,
                    "audio_seconds": round(r.audio_seconds, 1),
                    "time_to_first_interim_ms": r.time_to_first_interim_ms,
                    "time_to_first_final_ms": r.time_to_first_final_ms,
                    "keyword_coverage": round(r.keyword_coverage, 2),
                    "keywords_missed": r.keywords_missed,
                    "nudge_count": r.nudge_count,
                    "time_to_first_nudge_ms": r.time_to_first_nudge_ms,
                    "nudges": all_nudges[r.name],
                    "errors": r.errors,
                }
                for r in results
            ],
            "avg_keyword_coverage": round(avg_coverage, 2),
            "total_errors": total_errors,
        }
    )

    # Non-zero exit on a real regression -- any transport/pipeline error, or
    # coverage dropping enough to suggest transcription/streaming broke.
    return 0 if total_errors == 0 and avg_coverage >= 0.7 else 1


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
