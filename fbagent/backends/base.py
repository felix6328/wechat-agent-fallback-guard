"""Contracts shared by the evaluation runner and backend adapters."""
from typing import Protocol

from ..mock_apis import ToolResult


class Backend(Protocol):
    case_id: str
    calls: list[ToolResult]
    gt: dict[int, str | None]
    virtual_ms: float

    def call(self, op: str, args: dict) -> ToolResult: ...
    def harm(self) -> dict: ...
    def prepare_plan(self, plan: dict) -> dict: ...


class ProviderFailure(Exception):
    """A sanitized upstream failure that does not expose request URLs or keys."""

    def __init__(self, status: int, reason: str):
        self.status = status
        self.reason = reason
        super().__init__(reason)
