import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Central place for configuration. Deliberately simple for Phase 1 —
    no settings management library needed yet at this scale."""

    database_url: str = os.getenv(
        "DATABASE_URL",
        # 5433, not Postgres' default 5432 — see docker-compose.yml's db
        # port mapping comment. This fallback is only hit when running the
        # app on the host outside Docker; inside Docker, DATABASE_URL is
        # always set explicitly to db:5432 (the internal network port).
        "postgresql+psycopg2://signalhub:signalhub@localhost:5433/signalhub",
    )

    # Used by /extraction/infer to fill in the browser extension's preview
    # form (company/role/location/status) from page context. Server-side
    # only — never exposed to the extension's client-side code, since that
    # code ships in an unpacked/public repo where a key would leak
    # immediately. Extraction degrades to local heuristics when unset.
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY")


settings = Settings()
