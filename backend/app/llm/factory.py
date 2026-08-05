import logging

from app.config import settings
from app.llm.base import BaseLLMProvider
from app.llm.gemini_provider import GeminiProvider
from app.llm.groq_provider import GroqProvider
from app.llm.ollama_provider import OllamaProvider

logger = logging.getLogger("fitnova.llm")

_PROVIDERS = {
    "groq": GroqProvider,
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
}

# Fallback order when the configured primary provider errors out. Not
# specified explicitly in the design doc beyond "one env var swaps the
# provider" — this chain is an additive resilience feature: Groq (primary,
# fast) -> Gemini (cloud fallback) -> Ollama Cloud (last resort). All three
# share the same BaseLLMProvider interface, so this costs nothing extra.
_FALLBACK_ORDER = ["groq", "gemini", "ollama"]


def get_llm_provider(provider_name: str | None = None) -> BaseLLMProvider:
    """Instantiate one named LLM provider. Raises ValueError for an unknown
    name — use get_provider_chain() if you want missing/misconfigured
    providers silently skipped instead."""
    name = provider_name or settings.LLM_PROVIDER
    provider_cls = _PROVIDERS.get(name)
    if not provider_cls:
        raise ValueError(f"Unknown LLM_PROVIDER: {name}. Valid options: {list(_PROVIDERS)}")
    return provider_cls()


def get_provider_chain(primary: str | None = None) -> list[tuple[str, BaseLLMProvider]]:
    """Ordered (name, provider) pairs: configured primary first, then the
    remaining providers as fallbacks. A provider that fails to construct
    (e.g. missing API key) is skipped, not raised — callers should still end
    up with at least the primary provider unless it too is misconfigured."""
    primary = primary or settings.LLM_PROVIDER
    order = [primary] + [p for p in _FALLBACK_ORDER if p != primary]

    chain: list[tuple[str, BaseLLMProvider]] = []
    for name in order:
        try:
            chain.append((name, get_llm_provider(name)))
        except Exception as e:
            logger.warning("Skipping LLM provider %s (construction failed: %s)", name, e)
    return chain
