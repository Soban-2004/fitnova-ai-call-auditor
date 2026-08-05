import json

from groq import AsyncGroq

from app.config import settings
from app.llm.base import BaseLLMProvider, LLMProviderError


class GroqProvider(BaseLLMProvider):
    """Primary LLM provider — Groq's free tier (Llama 3.3 70B). Fast inference,
    generous free limits, reliable structured JSON output via response_format.
    """

    def __init__(self):
        self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self.model = settings.GROQ_MODEL

    async def complete(self, system_prompt: str, user_message: str, temperature: float = 0.0) -> dict:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=temperature,
                response_format={"type": "json_object"},
                max_tokens=4096,
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise LLMProviderError(f"Invalid JSON from Groq: {e}") from e
        except Exception as e:
            raise LLMProviderError(f"Groq API error: {e}") from e
