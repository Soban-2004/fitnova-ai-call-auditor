import json
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables / .env file.

    Nothing here is hardcoded into business logic — scoring weights and
    severity penalties are read as JSON strings so they can be tuned via
    env vars without a code change (see services/scoring.py).
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    DATABASE_URL: str

    # Deepgram
    DEEPGRAM_API_KEY: str = ""

    # LLM provider selection
    LLM_PROVIDER: str = "groq"

    # Groq
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # Gemini (fallback)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # Ollama Cloud (hosted fallback — defaults to https://ollama.com, not local)
    OLLAMA_BASE_URL: str = "https://ollama.com"
    OLLAMA_API_KEY: str = ""
    OLLAMA_MODEL: str = "gpt-oss:20b-cloud"

    # Scoring config (JSON strings — parsed by services/scoring.py)
    SCORING_WEIGHTS: str = (
        '{"needs_discovery":0.25,"product_knowledge":0.15,"objection_handling":0.15,'
        '"compliance":0.20,"trial_booking":0.15,"rapport_building":0.10}'
    )
    SEVERITY_PENALTIES: str = '{"critical":15,"major":8,"minor":3}'

    # Processing
    MAX_RETRIES: int = 3
    STUCK_CALL_TIMEOUT_MINUTES: int = 10
    POLL_INTERVAL_SECONDS: int = 5

    # CORS
    FRONTEND_URL: str = "http://localhost:3000"

    # Audio storage
    UPLOAD_DIR: str = "./uploads"

    @property
    def scoring_weights(self) -> dict[str, float]:
        return json.loads(self.SCORING_WEIGHTS)

    @property
    def severity_penalties(self) -> dict[str, int]:
        return json.loads(self.SEVERITY_PENALTIES)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
