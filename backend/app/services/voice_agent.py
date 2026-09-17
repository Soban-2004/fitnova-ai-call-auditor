"""Conversational state and reply generation for the automated voice intake
agent (routers/voice_agent.py) -- Stage 3 of fitnova's voice-AI roadmap.

Distinct from services/live_call.py: that module is a silent coaching
companion listening in on a human-run call. This one IS one side of the
conversation -- it listens (same Deepgram streaming STT, same speech_final/
UtteranceEnd turn-detection signals Stage 2 added), decides what to say via
the LLM, and speaks it back via Cartesia TTS (services/tts.py).
"""
import logging
from dataclasses import dataclass, field

from app.services.analysis import complete_with_fallback

logger = logging.getLogger("fitnova.voice_agent")

# Every LLM call in this codebase goes through providers that force JSON-mode
# responses (see llm/groq_provider.py, gemini_provider.py, ollama_provider.py
# -- all three unconditionally json.loads() the response), so this prompt
# must ask for JSON, not free-form spoken text.
_AGENT_SYSTEM_PROMPT = (
    "You are FitNova's automated intake assistant, having a real-time spoken "
    "conversation with a prospective customer who called in about a fitness "
    "membership. Every reply is spoken out loud -- keep it to one or two SHORT "
    "sentences, never written-prose length. Ask one question at a time, in this "
    "order: (0) their name, (1) a good callback number, (2) their main fitness "
    "goal, (3) any injuries or health conditions, (4) whether they're generally "
    "free weekday mornings, evenings, or weekends. Ask (0) right after your "
    "opening greeting, before anything else -- one fact per question, never "
    "two at once, and move to the next question the moment the current one is "
    "answered even loosely; don't re-ask something already answered. "
    "Once you have all five answers, do NOT just say an advisor will follow up --"
    " propose two concrete times for a follow-up call that fit what they told you "
    "about their availability (e.g. 'Would Tuesday at 6 PM or Wednesday at 7 PM "
    "work better?') and get them to pick one. Once they confirm a specific time, "
    "repeat it back to confirm the booking and say a FitNova advisor will call "
    "them then -- that confirmation line is your last turn, and "
    "conversation_done is only ever true on it, never on the line where you "
    "first proposed the times (that still needs their answer). Never invent "
    "pricing, plans, or promises; if asked about cost, say an advisor will cover "
    "pricing on that call. "
    'Respond with ONLY a JSON object: {"reply": "<one or two short spoken '
    'sentences>", "conversation_done": <true only on the final booking-'
    "confirmation line, else false>}."
)

_FALLBACK_REPLY = "Sorry, could you say that again?"


@dataclass
class VoiceAgentState:
    """Per-connection state -- one instance per voice-agent WebSocket
    connection (see routers/voice_agent.py), never shared across calls."""

    history: list[dict[str, str]] = field(default_factory=list)  # [{"role": "agent"|"caller", "text": ...}]
    done: bool = False
    # True from when the agent's audio is sent until it finishes -- routers/
    # voice_agent.py uses this to detect a barge-in (the caller talking
    # while this is still True) and tell the client to stop playback.
    agent_is_speaking: bool = False

    def add_turn(self, role: str, text: str) -> None:
        text = text.strip()
        if text:
            self.history.append({"role": role, "text": text})


def _format_history(history: list[dict[str, str]]) -> str:
    if not history:
        return "(the call just connected -- greet the caller and ask your first question)"
    return "\n".join(f"{turn['role']}: {turn['text']}" for turn in history)


async def generate_reply(state: VoiceAgentState) -> str:
    """Generates the agent's next spoken line given the conversation so far.
    Never raises and never returns an empty string -- on any failure this
    degrades to a fixed fallback line so the call stays alive with something
    to say, rather than the agent going silent on the caller.
    """
    try:
        # Caught live: the exact same (history, caller answer) pair produced
        # a correct "move to the next question" reply in one run and a
        # verbatim re-ask in another -- the turn-taking/buffer mechanics
        # were identical both times (confirmed via the router's own debug
        # log), so this is LLM judgment variance on "was this answered",
        # not a code bug. Same class of problem as live_call.py's nudge
        # repetition, which needed a deterministic code-level fix on top of
        # a prompt fix; this one doesn't have an equally cheap deterministic
        # check (there's no fixed string to compare against), so lowering
        # temperature -- trading a little reply variety for more consistent
        # "what's still unanswered" judgment -- is the first, cheaper lever.
        raw = await complete_with_fallback(
            _AGENT_SYSTEM_PROMPT,
            _format_history(state.history),
            temperature=0.15,
            purpose="voice_agent_reply",
        )
    except Exception as e:
        logger.warning("Voice agent reply generation failed: %s", e)
        return _FALLBACK_REPLY

    reply = raw.get("reply") if isinstance(raw, dict) else None
    if not reply or not isinstance(reply, str) or not reply.strip():
        return _FALLBACK_REPLY

    if raw.get("conversation_done") is True:
        state.done = True
    return reply.strip()


# A separate, one-shot extraction pass over the finished transcript, not
# tracked turn-by-turn during generate_reply -- keeps the live reply-
# generation prompt/schema unchanged (still just {"reply", "conversation_
# done"}) and reuses the same "ask an LLM for JSON" pattern already proven
# reliable here, rather than fragile positional parsing that assumes the
# agent always asks its four questions in exactly that order.
_LEAD_EXTRACTION_PROMPT = (
    "You are extracting structured lead information from a finished FitNova "
    "phone intake transcript, for the advisor who will follow up. Respond with "
    'ONLY a JSON object: {"customer_name": <string or null>, "customer_phone": '
    '<string or null>, "fitness_goal": <short string or null>, "health_notes": '
    '<short string or null>, "availability": <short string or null>, '
    '"confirmed_time": <short string or null -- the specific day/time booked '
    "for the follow-up call, if the transcript confirms one>}. Use null for "
    "anything not clearly stated. Never invent a value that isn't in the "
    "transcript."
)


async def extract_lead_info(history: list[dict[str, str]]) -> dict:
    """Best-effort structured extraction for the Lead this conversation
    becomes (see adapters/voice_agent.py / routers/voice_agent.py). Never
    raises -- a failed extraction just means a lead with fewer known
    fields, not a lost lead; the call itself is already safely persisted
    by the time this runs.
    """
    try:
        raw = await complete_with_fallback(
            _LEAD_EXTRACTION_PROMPT, _format_history(history), temperature=0.0, purpose="lead_extraction"
        )
        return raw if isinstance(raw, dict) else {}
    except Exception as e:
        logger.warning("Lead info extraction failed: %s", e)
        return {}
