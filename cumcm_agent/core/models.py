from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class LLMResponse:
    text: str
    model: str
    duration_seconds: float
    usage: dict[str, Any]
    cost_usd: float | None
    stderr: str


@dataclass
class StageRecord:
    stage: str
    status: str
    started_at: str
    ended_at: str
    duration_seconds: float
    outputs: list[str]
    model: str | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

