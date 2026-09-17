"""Cartesia TTS integration: turns the voice agent's LLM-generated reply
text into audio the caller actually hears. See services/voice_agent.py for
the conversational loop this feeds into, and routers/voice_agent.py for
where the resulting audio gets sent to the client.

Output is 16kHz mono WAV -- same sample rate as the mic-capture path
(services/live_call.SAMPLE_RATE), so the frontend needs no separate
resampling logic for agent audio vs. what it already sends. WAV specifically
(not raw PCM) because it's a real, self-describing container the browser's
native <audio>/Audio() can play directly with zero client-side decoding
work, unlike raw PCM which needs an AudioContext buffer to be built by hand.
"""
import logging

from cartesia import AsyncCartesia

from app.config import settings
from app.services.telemetry import track_llm_call

logger = logging.getLogger("fitnova.tts")

SAMPLE_RATE = 16000

_client: AsyncCartesia | None = None


def _get_client() -> AsyncCartesia:
    global _client
    if _client is None:
        _client = AsyncCartesia(api_key=settings.CARTESIA_API_KEY)
    return _client


async def synthesize(text: str) -> bytes | None:
    """Returns WAV audio bytes for `text`, or None if TTS is unconfigured or
    the call fails. A TTS outage must never break the conversation -- the
    caller (routers/voice_agent.py) degrades to sending the reply as text
    only rather than dropping the turn entirely.
    """
    if not settings.CARTESIA_API_KEY or not text.strip():
        return None

    try:
        # track_llm_call re-raises after recording telemetry -- caught below,
        # same "degrade, never crash the conversation" contract as every
        # other provider call in this codebase.
        async with track_llm_call("cartesia", settings.CARTESIA_MODEL, "voice_agent_tts"):
            response = await _get_client().tts.generate(
                model_id=settings.CARTESIA_MODEL,
                transcript=text,
                voice={"id": settings.CARTESIA_VOICE_ID},
                output_format={"container": "wav", "encoding": "pcm_s16le", "sample_rate": SAMPLE_RATE},
            )
            chunks = [chunk async for chunk in response.iter_bytes()]
        audio = b"".join(chunks)
        return audio or None
    except Exception as e:
        logger.warning("Cartesia TTS synthesis failed, degrading to text-only: %s", e)
        return None
