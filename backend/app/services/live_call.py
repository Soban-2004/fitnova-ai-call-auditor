"""Real-time voice coaching: sliding-window transcript state and nudge
generation for a live call session.

Stage 1 of moving fitnova from a post-call analytics pipeline (upload a
finished recording -> batch-transcribe -> analyze) to a genuine real-time
voice AI system: audio is streamed in as the call happens, transcribed via
Deepgram's *streaming* API (not the batch one services/transcription.py
uses), and this module decides, as new utterances arrive, whether the
advisor needs a short actionable nudge right now.

Stage 2 adds real turn detection: Deepgram's own VAD (`vad_events=True`,
`utterance_end_ms` in routers/live.py's LiveOptions) was enabled from the
start but nothing consumed its events. Two things now do: a nudge check is
gated on `is_speaking` being False (never interrupt someone mid-sentence
with a coaching popup), and UtteranceEnd -- a dedicated "the speaker has
genuinely paused" signal, distinct from a per-segment `is_final` transcript
event -- is a second, more reliable trigger for checking whether a nudge is
due, alongside the existing final-transcript trigger.

This module owns the pure logic (sliding window, nudge cadence, prompting).
The Deepgram connection lifecycle and the client-facing WebSocket live in
routers/live.py — kept separate the same way processor.py (orchestration)
and services/analysis.py (LLM logic) are already split in this codebase.

Stage "Advisor path" adds persistence: a finished session becomes a real,
scored `calls` row (adapters/live_call.py), the same way a voice-agent
conversation already does (adapters/voice_agent.py). The nudge-generation
sliding window (`utterances`, plain text) stays role-agnostic on purpose --
that logic is already proven and untouched here -- but `segments` tracks
per-final-transcript speaker labels (from Deepgram's live diarization, word-
level `speaker` field majority-voted per segment) purely for that
persistence path. Speaker *role* (advisor vs. customer) is deliberately
NOT resolved here -- unlike the voice agent, where the roles are known by
construction, a live session's diarized "Speaker 0/1" genuinely needs the
same LLM speaker-ID pass a normal upload gets; see processor.py's
speaker_roles_known check.
"""
import logging
import time
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from app.services.analysis import complete_with_fallback

logger = logging.getLogger("fitnova.live_call")

# Deepgram streaming audio format this module expects -- see routers/live.py's
# LiveOptions. Raw PCM, not a container format (webm/mp3), so there's no
# encoder/decoder round-trip between the browser and Deepgram to add latency.
SAMPLE_RATE = 16000
ENCODING = "linear16"
CHANNELS = 1

# How often the sliding window is re-checked for a fresh nudge -- not every
# single final utterance (that would spam the advisor and burn an LLM call
# every few seconds), not too sparse either (defeats the point of "in the
# moment"). Both conditions must hold before a nudge is even attempted.
NUDGE_MIN_INTERVAL_SECONDS = 12.0
NUDGE_MIN_NEW_UTTERANCES = 2
NUDGE_WINDOW_UTTERANCES = 12  # how much recent context the nudge prompt sees

# scripts/eval_live_call.py caught this live: on a short call with a stable
# topic, consecutive nudge rounds see largely overlapping transcript window
# and independently arrive at near-identical advice ("ask about their goals"
# three times, reworded) -- the system prompt's "never restate" instruction
# has nothing to check against since it only ever sees the transcript, never
# its own prior output. Feeding back the last few nudges fixes most of this.
NUDGE_HISTORY_SIZE = 5

# The prompt-level fix above is a soft instruction, not a guarantee -- caught
# live in the very next eval run: the model repeated an earlier nudge
# *verbatim* even with that nudge sitting right there in "already given"
# context. A prompt asking the model not to repeat itself is advisory; this
# threshold is enforced in code regardless of what the model does. RapidFuzz
# is already a dependency here (see services/validation.py's Layer 2 quote
# matching) -- same tool, same "don't trust free-form LLM compliance"
# philosophy, reused rather than hand-rolling a second string-similarity check.
NUDGE_DUPLICATE_THRESHOLD = 80  # fuzz.ratio 0-100; empirically, near-identical phrasing scores 85+

# Every LLM call in this codebase goes through providers that force JSON-mode
# responses (see llm/groq_provider.py, gemini_provider.py, ollama_provider.py
# -- all three unconditionally json.loads() the response), so this prompt
# must ask for JSON, not a bare sentence or a sentinel string.
_NUDGE_SYSTEM_PROMPT = (
    "You are a real-time sales coaching assistant listening to a live sales call. "
    "You see only the most recent portion of the conversation, not the full call. "
    "Decide whether the advisor needs a short, actionable nudge RIGHT NOW -- a missed "
    "discovery question, an unaddressed objection, a compliance risk (false urgency, "
    "unrealistic guarantees, undisclosed costs), or a good moment to move toward booking. "
    'Respond with ONLY a JSON object: {"nudge": "<one short sentence, under 15 words, the '
    'advisor could act on immediately>"} if something is genuinely useful right now, or '
    '{"nudge": null} if there is nothing useful to say. Do not narrate what already '
    "happened, and never restate something already obvious from the transcript. You will "
    "also be shown the nudges you already gave earlier in this same call -- if the only "
    "thing worth saying is a rewording of one of those, respond with null instead."
)


@dataclass
class LiveCallState:
    """Per-connection state -- one instance per live-call WebSocket
    connection (see routers/live.py), never shared across calls."""

    utterances: list[str] = field(default_factory=list)
    last_nudge_at: float = 0.0
    utterances_since_last_nudge: int = 0
    recent_nudges: list[str] = field(default_factory=list)
    # Driven by Deepgram's SpeechStarted/UtteranceEnd events (see
    # routers/live.py) -- True while someone is actively mid-utterance.
    is_speaking: bool = False
    # Diarized segments for persistence (adapters/live_call.py) -- kept
    # separate from `utterances` above so the already-proven nudge logic
    # never has to change shape.
    segments: list[dict] = field(default_factory=list)

    def add_final_utterance(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        self.utterances.append(text)
        self.utterances_since_last_nudge += 1

    def add_final_segment(self, speaker_label: str, text: str, start_ts: float, end_ts: float) -> None:
        text = text.strip()
        if not text:
            return
        self.segments.append(
            {"speaker_label": speaker_label, "text": text, "start_ts": start_ts, "end_ts": end_ts}
        )

    def record_nudge(self, text: str) -> None:
        self.recent_nudges.append(text)
        self.recent_nudges = self.recent_nudges[-NUDGE_HISTORY_SIZE:]


def _format_window(utterances: list[str]) -> str:
    return "\n".join(utterances[-NUDGE_WINDOW_UTTERANCES:])


async def maybe_generate_nudge(state: LiveCallState) -> str | None:
    """Returns a nudge string if one is due and the LLM produced something
    actionable, else None. Never raises -- a nudge-generation failure
    degrades to "no nudge this round", it must never interrupt the live
    transcript stream the advisor is actively relying on.
    """
    if state.is_speaking:
        # Never surface a coaching popup while someone is actively
        # mid-sentence -- wait for the natural pause UtteranceEnd/a final
        # transcript represents. Checked first since it's the cheapest test.
        return None
    if state.utterances_since_last_nudge < NUDGE_MIN_NEW_UTTERANCES:
        return None
    now = time.monotonic()
    if now - state.last_nudge_at < NUDGE_MIN_INTERVAL_SECONDS:
        return None
    if not state.utterances:
        return None

    # Reset before the (slow) LLM call, not after -- so utterances that
    # arrive *during* generation count toward the next round's threshold
    # instead of being silently absorbed into this one.
    state.last_nudge_at = now
    state.utterances_since_last_nudge = 0

    window = _format_window(state.utterances)
    user_message = f"Recent transcript:\n{window}"
    if state.recent_nudges:
        prior = "\n".join(f"- {n}" for n in state.recent_nudges)
        user_message += f"\n\nNudges already given earlier in this call:\n{prior}"

    try:
        raw = await complete_with_fallback(
            _NUDGE_SYSTEM_PROMPT,
            user_message,
            temperature=0.3,
            purpose="live_nudge",
        )
    except Exception as e:
        logger.warning("Live nudge generation failed, skipping this round: %s", e)
        return None

    nudge = raw.get("nudge") if isinstance(raw, dict) else None
    if not nudge or not isinstance(nudge, str):
        return None
    nudge = nudge.strip()

    if any(fuzz.ratio(nudge.lower(), prior.lower()) >= NUDGE_DUPLICATE_THRESHOLD for prior in state.recent_nudges):
        logger.info("Live nudge suppressed as a near-duplicate of a prior one: %r", nudge)
        return None

    state.record_nudge(nudge)
    return nudge
