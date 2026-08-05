import json

import google.generativeai as genai

from app.config import settings
from app.llm.base import BaseLLMProvider, LLMProviderError


class GeminiProvider(BaseLLMProvider):
    """Fallback LLM provider — Google Gemini free tier. Used when Groq is
    down/rate-limited or when LLM_PROVIDER=gemini is set explicitly.
    """

    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise LLMProviderError("GEMINI_API_KEY is not set")
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model_name = settings.GEMINI_MODEL

    async def complete(self, system_prompt: str, user_message: str, temperature: float = 0.0) -> dict:
        try:
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system_prompt,
                generation_config={
                    "temperature": temperature,
                    "response_mime_type": "application/json",
                },
            )
            response = await model.generate_content_async(user_message)
            return json.loads(response.text)
        except json.JSONDecodeError as e:
            raise LLMProviderError(f"Invalid JSON from Gemini: {e}") from e
        except Exception as e:
            raise LLMProviderError(f"Gemini API error: {e}") from e
