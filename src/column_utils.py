"""Utilities for normalizing tabular column names."""

from __future__ import annotations

import re
from collections.abc import Iterable


def clean_column_names(columns: Iterable[object]) -> list[str]:
    """Return safe, normalized, and unique column names."""
    seen: dict[str, int] = {}
    cleaned: list[str] = []

    for original in columns:
        base = re.sub(
            r"[^0-9a-zA-Z]+",
            "_",
            str(original).strip(),
        ).strip("_").lower()
        base = base or "unnamed"

        count = seen.get(base, 0)
        seen[base] = count + 1
        cleaned.append(base if count == 0 else f"{base}_{count}")

    return cleaned
