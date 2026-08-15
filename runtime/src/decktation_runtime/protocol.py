"""Protocol scaffolding for the future runtime bridge."""

from dataclasses import dataclass, field


@dataclass
class RuntimeRequest:
    id: str
    method: str
    params: dict = field(default_factory=dict)


@dataclass
class RuntimeResponse:
    id: str
    ok: bool
    result: dict | None = None
    error: str | None = None


@dataclass
class RuntimeEvent:
    event: str
    payload: dict = field(default_factory=dict)
