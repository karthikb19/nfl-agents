# backend/config.py
import os
from functools import lru_cache

from dotenv import load_dotenv, find_dotenv


@lru_cache
def _load_env() -> None:
    # Ensure dotenv is loaded exactly once across the whole process
    load_dotenv(find_dotenv())


@lru_cache
def get_db_url() -> str:
    _load_env()
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise RuntimeError("SUPABASE_DB_URL is not set in the environment")

    # Strip ?pgbouncer=... for psycopg2 compatibility
    if "?pgbouncer=" in db_url:
        db_url = db_url.split("?pgbouncer=")[0]

    return db_url


@lru_cache
def get_openrouter_api_key() -> str:
    _load_env()
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set in the environment")
    return key


MODEL = "google/gemini-2.5-flash-lite"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def get_openrouter_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {get_openrouter_api_key()}",
        "Content-Type": "application/json",
    }
