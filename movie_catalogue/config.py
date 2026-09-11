import os
from pathlib import Path

from .password_policy import password_min_length


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def default_database_path() -> str:
    return os.getenv("DATABASE_PATH", "/data/movies.db")


class Config:
    APP_NAME = "Homebuster"
    APP_VERSION = "0.3.4"
    DATABASE_PATH = default_database_path()
    SECRET_KEY = os.getenv("SECRET_KEY", "")
    ALLOW_REGISTRATION = env_bool("ALLOW_REGISTRATION", False)
    PASSWORD_MIN_LENGTH = password_min_length(os.environ)
    INITIAL_ADMIN_USERNAME = os.getenv("INITIAL_ADMIN_USERNAME", "")
    INITIAL_ADMIN_PASSWORD = os.getenv("INITIAL_ADMIN_PASSWORD", "")
    TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
    TMDB_POSTER_SIZE = os.getenv("TMDB_POSTER_SIZE", "w342")
    UPCITEMDB_API_KEY = os.getenv("UPCITEMDB_API_KEY", "")
    UPCITEMDB_FREE_ENABLED = env_bool("UPCITEMDB_FREE_ENABLED", False)
    BARCODE_LOOKUP_URL = os.getenv("BARCODE_LOOKUP_URL", "")
    PAGE_SIZE = int(os.getenv("PAGE_SIZE", "60"))
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", False)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
