from __future__ import annotations

from uuid import uuid4


def generate_identifier(prefix: str | None = None) -> str:
    """
    Generate a unique platform identifier.

    Example:
        run_4e2fa0f9e6514b98aee16a26a364be81
    """

    value = uuid4().hex

    normalized_prefix = str(prefix or "").strip().lower()

    if not normalized_prefix:
        return value

    return f"{normalized_prefix}_{value}"