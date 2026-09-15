"""Festival calendar ? loaded from config/calendar.yaml, with fallback defaults."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Festival:
    name: str
    date: date
    surge_days_before: int
    surge_days_after: int
    multiplier: float


# Fallback set used when config/calendar.yaml is absent or empty.
# Name, ISO date, days before, days after, multiplier.
_DEFAULT_FESTIVALS: tuple[tuple[str, str, int, int, float], ...] = (
    ("Republic Day", "2025-01-26", 2, 1, 1.15),
    ("Holi", "2025-03-14", 3, 2, 1.25),
    ("Eid al-Fitr", "2025-03-31", 3, 1, 1.20),
    ("Independence Day", "2025-08-15", 2, 1, 1.15),
    ("Diwali", "2025-10-20", 5, 3, 1.45),
    ("Christmas", "2025-12-25", 3, 2, 1.25),
)


def _read_yaml(path: Path) -> list[dict[str, Any]] | None:
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(data, dict):
        return None
    items = data.get("festivals")
    if not isinstance(items, list) or not items:
        return None
    return items


def _defaults() -> tuple[Festival, ...]:
    return tuple(
        Festival(
            name=n,
            date=date.fromisoformat(d),
            surge_days_before=b,
            surge_days_after=a,
            multiplier=m,
        )
        for n, d, b, a, m in _DEFAULT_FESTIVALS
    )


def load_festivals(config_dir: Path) -> tuple[Festival, ...]:
    """Return festivals from config/calendar.yaml, or built-in defaults."""
    raw = _read_yaml(config_dir / "calendar.yaml")
    if raw is None:
        return _defaults()
    parsed: list[Festival] = []
    for item in raw:
        try:
            parsed.append(
                Festival(
                    name=str(item["name"]),
                    date=date.fromisoformat(str(item["date"])),
                    surge_days_before=int(item.get("surge_days_before", 2)),
                    surge_days_after=int(item.get("surge_days_after", 1)),
                    multiplier=float(item["multiplier"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            # Skip malformed entries rather than crashing the whole run.
            continue
    return tuple(parsed) if parsed else _defaults()


def festival_multiplier(d: date, festivals: tuple[Festival, ...]) -> float:
    """Return the highest applicable multiplier on date d, or 1.0.

    On the festival date the full multiplier applies. Before and after,
    the surge decays linearly back to 1.0 over the configured window.
    If two festivals overlap, the highest surge wins.
    """
    best = 1.0
    for f in festivals:
        delta = (d - f.date).days
        if delta == 0:
            candidate = f.multiplier
        elif -f.surge_days_before <= delta < 0:
            span = f.surge_days_before + 1
            frac = 1.0 - (abs(delta) / span)
            candidate = 1.0 + (f.multiplier - 1.0) * frac
        elif 0 < delta <= f.surge_days_after:
            span = f.surge_days_after + 1
            frac = 1.0 - (delta / span)
            candidate = 1.0 + (f.multiplier - 1.0) * frac
        else:
            continue
        best = max(best, candidate)
    return best
