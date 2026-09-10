from __future__ import annotations

from collections.abc import Mapping

DEFAULT_PASSWORD_MIN_LENGTH = 8


def password_min_length(config: Mapping) -> int:
    """Return the configured minimum password length, safely normalized."""
    raw = config.get("PASSWORD_MIN_LENGTH", DEFAULT_PASSWORD_MIN_LENGTH)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_PASSWORD_MIN_LENGTH
    return value if value >= 1 else DEFAULT_PASSWORD_MIN_LENGTH


def password_length_error(password: str, config: Mapping, *, label: str = "Password") -> str | None:
    minimum = password_min_length(config)
    if len(password) < minimum:
        return f"{label} must be at least {minimum} characters."
    return None
