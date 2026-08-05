from abc import ABC, abstractmethod
from typing import Any


class LLMProviderError(Exception):
    """Raised when an LLM provider call fails (API error, timeout, or invalid JSON)."""
    pass


class BaseLLMProvider(ABC):
    """Abstract base for LLM providers. All providers return parsed JSON dicts.

    Swapping providers is a one-line env var change (LLM_PROVIDER=groq|gemini|ollama) —
    see llm/factory.py. No framework dependency (no LangChain/LiteLLM); this
    abstraction is deliberately thin.
    """

    @abstractmethod
    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        """
        Send a completion request and return parsed JSON.

        Args:
            system_prompt: System instruction text.
            user_message: User/input text (the transcript).
            temperature: Sampling temperature (default 0 for deterministic output).

        Returns:
            Parsed JSON dict from the model's response.

        Raises:
            LLMProviderError: On API failure, timeout, or invalid JSON response.
        """
        raise NotImplementedError
