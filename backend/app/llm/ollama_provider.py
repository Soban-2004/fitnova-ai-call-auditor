import json

import httpx

from app.config import settings
from app.llm.base import BaseLLMProvider, LLMProviderError


class OllamaProvider(BaseLLMProvider):
    """Local-cost-free fallback via Ollama's hosted Cloud API (https://ollama.com).

    This is a REST call to Ollama's native /api/chat endpoint (not the
    OpenAI-compatible /v1 layer), authenticated with a bearer API key from
    https://ollama.com/settings/keys. Same interface as every other provider —
    only OLLAMA_BASE_URL/OLLAMA_API_KEY differ if pointed at a local daemon
    instead (http://localhost:11434, no key needed).
    """

    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.api_key = settings.OLLAMA_API_KEY
        self.model = settings.OLLAMA_MODEL

    async def complete(self, system_prompt: str, user_message: str, temperature: float = 0.0) -> dict:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": temperature},
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                content = data["message"]["content"]
                return json.loads(content)
        except json.JSONDecodeError as e:
            raise LLMProviderError(f"Invalid JSON from Ollama: {e}") from e
        except httpx.HTTPStatusError as e:
            raise LLMProviderError(f"Ollama API error: {e.response.status_code} {e.response.text}") from e
        except Exception as e:
            raise LLMProviderError(f"Ollama request failed: {e}") from e
