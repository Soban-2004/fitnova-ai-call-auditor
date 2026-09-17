import json

from groq import AsyncGroq

from app.config import settings
from app.llm.base import BaseLLMProvider, LLMProviderError


class GroqProvider(BaseLLMProvider):
    """Primary LLM provider — Groq's free tier. Reliable structured JSON
    output via response_format.

    GROQ_MODEL was llama-3.3-70b-versatile (not a reasoning model) until
    Groq deprecated it 2026-08-16; openai/gpt-oss-20b, their recommended
    replacement, IS a reasoning model — it spends part of its completion
    budget on an internal trace before the actual JSON answer, and under
    json_object mode that occasionally consumes the entire budget, producing
    a 400 (json_validate_failed, empty failed_generation) instead of an
    answer — confirmed live via scripts/eval_issue_detection.py, ~1-in-3
    calls, plus successful calls taking ~20s+ (the trace itself is slow to
    generate). reasoning_effort="low" is the fix already proven for this
    exact failure mode elsewhere in this codebase's history: it bounds the
    trace instead of leaving it unmanaged. Only passed for the gpt-oss
    family — an actual non-reasoning model (like the old default) rejects
    an unrecognized param outright.
    """

    _REASONING_MODEL_PREFIXES = ("openai/gpt-oss",)

    def __init__(self):
        self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self.model = settings.GROQ_MODEL

    async def complete(self, system_prompt: str, user_message: str, temperature: float = 0.0) -> dict:
        kwargs = {}
        if self.model.startswith(self._REASONING_MODEL_PREFIXES):
            # groq==0.15.0's typed create() predates this param -- extra_body
            # passes it straight through in the request JSON regardless, the
            # SDK's own documented escape hatch for exactly this situation.
            kwargs["extra_body"] = {"reasoning_effort": "low"}
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
                **kwargs,
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise LLMProviderError(f"Invalid JSON from Groq: {e}") from e
        except Exception as e:
            raise LLMProviderError(f"Groq API error: {e}") from e
