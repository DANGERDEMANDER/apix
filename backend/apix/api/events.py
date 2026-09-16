"""In-process event bus for live collection runs."""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

EventLevel = Literal["info", "warn", "error", "success"]


@dataclass(frozen=True)
class ProgressEvent:
    at: str
    level: EventLevel
    stage: str
    message: str
    detail: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "at": self.at,
            "level": self.level,
            "stage": self.stage,
            "message": self.message,
            "detail": self.detail,
        }


@dataclass
class RunChannel:
    """One queue per run. Closed when the run finishes."""

    run_id: str
    queue: asyncio.Queue[ProgressEvent | None] = field(
        default_factory=lambda: asyncio.Queue(maxsize=2048)
    )
    finished: bool = False

    async def emit(self, level: EventLevel, stage: str, message: str, **detail: object) -> None:
        if self.finished:
            return
        ev = ProgressEvent(
            at=datetime.now(timezone.utc).isoformat(),
            level=level,
            stage=stage,
            message=message,
            detail=dict(detail),
        )
        with contextlib.suppress(asyncio.QueueFull):
            self.queue.put_nowait(ev)  # drop rather than block the collector

    async def close(self) -> None:
        self.finished = True
        with contextlib.suppress(asyncio.QueueFull):
            self.queue.put_nowait(None)


_channels: dict[str, RunChannel] = {}


def new_channel() -> RunChannel:
    ch = RunChannel(run_id=uuid.uuid4().hex[:12])
    _channels[ch.run_id] = ch
    return ch


def get_channel(run_id: str) -> RunChannel | None:
    return _channels.get(run_id)


def drop_channel(run_id: str) -> None:
    _channels.pop(run_id, None)
