import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Central place for configuration. Deliberately simple for Phase 1 —
    no settings management library needed yet at this scale."""

    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://signalhub:signalhub@localhost:5432/signalhub",
    )


settings = Settings()
