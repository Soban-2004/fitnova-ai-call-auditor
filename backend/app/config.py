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
    # llama-3.3-70b-versatile was deprecated by Groq on 2026-08-16
    # (console.groq.com/docs/deprecations) -- confirmed live via
    # scripts/eval_issue_detection.py, which caught every single call 404ing
    # and silently falling through to the Ollama tier. openai/gpt-oss-20b is
    # Groq's own recommended replacement.
    GROQ_MODEL: str = "openai/gpt-oss-20b"

    # Gemini (fallback)
    GEMINI_API_KEY: str = ""
    # gemini-2.0-flash was retired -- also caught live by the same eval run
    # above (404, "no longer available... use models/gemini-3.6-flash").
    GEMINI_MODEL: str = "gemini-3.6-flash"

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

    # Backblaze B2 (S3-compatible) — durable copy of uploaded audio. All
    # blank by default: B2 is optional, not required to run the app. See
    # services/audio_storage.py.
    B2_ENDPOINT_URL: str = ""
    B2_BUCKET_NAME: str = ""
    B2_KEY_ID: str = ""
    B2_APPLICATION_KEY: str = ""

    # Upload rate limiting -- see services/rate_limit.py for why this exists
    # (POST /api/upload has no auth at all).
    UPLOAD_RATE_LIMIT_MAX_PER_WINDOW: int = 5
    UPLOAD_RATE_LIMIT_WINDOW_SECONDS: int = 600
    UPLOAD_DAILY_CAP: int = 100
    # Generous for a real call recording (a 30-minute call is a few MB even
    # uncompressed), well short of anything pathological. Checked after
    # read() but before the file is written to disk — see adapters/
    # file_upload.py.
    MAX_UPLOAD_SIZE_BYTES: int = 50_000_000

    # Shared-secret gate for GET /api/admin/llm-stats (see services/
    # telemetry.py) -- this app has no user auth system at all to hang a
    # real admin role off of, so a single static token is the pragmatic
    # option. Empty means the endpoint is closed to everyone, same
    # "unconfigured by default" pattern as the B2/OLLAMA settings above.
    ADMIN_TOKEN: str = ""

    # Cartesia TTS -- the voice agent's spoken output (services/tts.py,
    # routers/voice_agent.py). Empty means the feature is unconfigured (the
    # agent degrades to text-only responses, never crashes), same pattern as
    # every other optional integration above. sonic-latest tracks Cartesia's
    # current model automatically rather than pinning a dated version --
    # already learned that lesson twice this session with Groq/Gemini model
    # deprecations breaking a hardcoded name outright.
    CARTESIA_API_KEY: str = ""
    CARTESIA_MODEL: str = "sonic-latest"
    # "Skylar", a stock English voice -- picked via the real /voices list,
    # not guessed. Swap freely; any valid Cartesia voice ID works here.
    CARTESIA_VOICE_ID: str = "db6b0ed5-d5d3-463d-ae85-518a07d3c2b4"

    # The voice agent (routers/voice_agent.py) is treated as a virtual
    # advisor, not a special case bolted onto the schema: its finished
    # conversations become real `calls` rows (source_system="voice_agent")
    # owned by this fixed advisor id, scored by the exact same pipeline as
    # a human's. That's what makes it show up on the Team/Director
    # dashboards for free -- see scripts/seed_db.py, which seeds this
    # advisor under a dedicated "AI Agents" team.
    AI_AGENT_ADVISOR_ID: str = "c0000000-0000-0000-0000-000000000007"

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
