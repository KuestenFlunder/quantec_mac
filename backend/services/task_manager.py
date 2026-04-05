"""Background task manager for async scan/send operations.

Runs hardware-bound operations (scans, sends) as asyncio background tasks.
Each task gets a unique ID so the frontend can poll status and retrieve results.
"""

from __future__ import annotations

import asyncio
import enum
import logging
import time
import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Keep at most this many completed/failed tasks in memory
MAX_HISTORY = 200


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BackgroundTask:
    task_id: str
    task_type: str
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str | None = None
    created_at: float = field(default_factory=time.monotonic)
    started_at: float | None = None
    finished_at: float | None = None
    progress: float = 0.0
    _cancel_flag: bool = field(default=False, repr=False)
    _asyncio_task: asyncio.Task | None = field(default=None, repr=False)

    def request_cancel(self) -> None:
        self._cancel_flag = True
        if self._asyncio_task and not self._asyncio_task.done():
            self._asyncio_task.cancel()

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_flag

    @property
    def elapsed_seconds(self) -> float | None:
        if self.started_at is None:
            return None
        end = self.finished_at or time.monotonic()
        return end - self.started_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
            "elapsed_seconds": self.elapsed_seconds,
        }


class TaskManager:
    """Singleton-style manager for background tasks.

    Usage (from async context):
        mgr = TaskManager()
        task = await mgr.submit("send", send_coroutine_fn, sheet_id=5, duration=120)
        status = mgr.get(task.task_id)
        mgr.cancel(task.task_id)
    """

    def __init__(self) -> None:
        self._tasks: dict[str, BackgroundTask] = {}

    async def submit(
        self,
        task_type: str,
        coro_fn: Callable[..., Coroutine[Any, Any, Any]],
        **kwargs: Any,
    ) -> BackgroundTask:
        """Create and schedule a background task.

        Must be called from an async context (within the running event loop).

        Args:
            task_type: Label like 'scan', 'send', 'butler_check'.
            coro_fn: Async callable that receives (bg_task, **kwargs).
                     It should update bg_task.progress and bg_task.result.
            **kwargs: Passed through to coro_fn.

        Returns:
            The BackgroundTask handle (status starts as PENDING, transitions to RUNNING).
        """
        task_id = uuid.uuid4().hex[:12]
        bg_task = BackgroundTask(task_id=task_id, task_type=task_type)
        self._tasks[task_id] = bg_task

        loop = asyncio.get_running_loop()
        asyncio_task = loop.create_task(self._run(bg_task, coro_fn, **kwargs))
        bg_task._asyncio_task = asyncio_task

        self._evict_old()
        return bg_task

    async def _run(
        self,
        bg_task: BackgroundTask,
        coro_fn: Callable[..., Coroutine[Any, Any, Any]],
        **kwargs: Any,
    ) -> None:
        bg_task.status = TaskStatus.RUNNING
        bg_task.started_at = time.monotonic()
        try:
            result = await coro_fn(bg_task, **kwargs)
            if bg_task.is_cancelled:
                bg_task.status = TaskStatus.CANCELLED
            else:
                bg_task.status = TaskStatus.COMPLETED
                bg_task.result = result
        except asyncio.CancelledError:
            bg_task.status = TaskStatus.CANCELLED
            logger.info("Task %s cancelled", bg_task.task_id)
        except Exception as exc:
            bg_task.status = TaskStatus.FAILED
            bg_task.error = str(exc)
            logger.exception("Task %s failed", bg_task.task_id)
        finally:
            bg_task.finished_at = time.monotonic()
            bg_task.progress = 1.0 if bg_task.status == TaskStatus.COMPLETED else bg_task.progress

    def get(self, task_id: str) -> BackgroundTask | None:
        return self._tasks.get(task_id)

    def get_all(self, task_type: str | None = None) -> list[BackgroundTask]:
        tasks = list(self._tasks.values())
        if task_type:
            tasks = [t for t in tasks if t.task_type == task_type]
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)

    def cancel(self, task_id: str) -> bool:
        bg_task = self._tasks.get(task_id)
        if bg_task is None:
            return False
        if bg_task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            return False
        bg_task.request_cancel()
        return True

    def _evict_old(self) -> None:
        """Remove oldest completed/failed tasks when history exceeds MAX_HISTORY."""
        terminal = [
            t for t in self._tasks.values()
            if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
        ]
        if len(terminal) <= MAX_HISTORY:
            return
        terminal.sort(key=lambda t: t.created_at)
        for t in terminal[: len(terminal) - MAX_HISTORY]:
            self._tasks.pop(t.task_id, None)


# Module-level singleton
task_manager = TaskManager()
