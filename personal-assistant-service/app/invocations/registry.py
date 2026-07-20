from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from app.invocations.service import InvocationExecution


@dataclass(frozen=True)
class InvocationKey:
    user_id: str
    conversation_id: UUID
    client_message_id: UUID


class InvocationRegistry:
    def __init__(self) -> None:
        self._executions: dict[InvocationKey, InvocationExecution] = {}

    def register(
        self,
        *,
        key: InvocationKey,
        execution: InvocationExecution,
    ) -> None:
        if key in self._executions:
            raise RuntimeError("invocation is already registered")
        self._executions[key] = execution

    def unregister(
        self,
        *,
        key: InvocationKey,
        execution: InvocationExecution,
    ) -> None:
        if self._executions.get(key) is execution:
            del self._executions[key]

    async def cancel(self, *, key: InvocationKey) -> bool:
        execution = self._executions.get(key)
        if execution is None:
            return False
        await execution.cancel()
        return True
