"""Send service -- orchestrates HealingSheet sending via the diode hardware.

Loads a HealingSheet with its items from the database, runs BasicDiode.send()
for the requested duration, and records a SendJob entry.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from database import SessionLocal
from hardware import BasicDiode, MockDevice
from hardware.ftdi import DeviceInterface
from models.healing_sheet import HealingSheet
from models.schedule import Schedule, SendJob
from services.task_manager import BackgroundTask, task_manager

logger = logging.getLogger(__name__)

# Module-level device reference -- set via init_device() at startup
_device: DeviceInterface | None = None


def init_device(device: DeviceInterface | None = None) -> DeviceInterface:
    """Initialize the hardware device (or MockDevice for development)."""
    global _device
    if device is not None:
        _device = device
    elif _device is None:
        _device = MockDevice()
        _device.open()
    return _device


def get_device() -> DeviceInterface:
    if _device is None:
        return init_device()
    return _device


class SendService:
    """Service for sending HealingSheets through the diode."""

    @staticmethod
    async def start_send(sheet_id: int, duration: float, schedule_id: int | None = None) -> BackgroundTask:
        """Start a background send operation.

        Must be called from an async context.

        Args:
            sheet_id: HealingSheet to send.
            duration: Send duration in seconds.
            schedule_id: Optional schedule to link the SendJob to.

        Returns:
            BackgroundTask handle for status polling.
        """
        return await task_manager.submit(
            "send",
            SendService._send_coro,
            sheet_id=sheet_id,
            duration=duration,
            schedule_id=schedule_id,
        )

    @staticmethod
    async def _send_coro(
        bg_task: BackgroundTask,
        *,
        sheet_id: int,
        duration: float,
        schedule_id: int | None,
    ) -> dict:
        """Async coroutine that performs the send in a thread."""
        db: Session = SessionLocal()
        try:
            # Load the sheet with items
            stmt = (
                select(HealingSheet)
                .options(joinedload(HealingSheet.items))
                .where(HealingSheet.id == sheet_id)
            )
            sheet = db.scalars(stmt).unique().one_or_none()
            if sheet is None:
                raise ValueError(f"HealingSheet {sheet_id} not found")

            item_count = len(sheet.items)

            # Resolve or create schedule for the SendJob
            resolved_schedule_id = schedule_id
            if resolved_schedule_id is None:
                # Find an active schedule for this sheet
                sched_stmt = (
                    select(Schedule)
                    .where(Schedule.healing_sheet_id == sheet_id, Schedule.active.is_(True))
                    .limit(1)
                )
                sched = db.scalars(sched_stmt).first()
                if sched:
                    resolved_schedule_id = sched.id
                else:
                    # Create an ad-hoc schedule
                    sched = Schedule(
                        healing_sheet_id=sheet_id,
                        schedule_type="ad_hoc",
                        active=False,
                    )
                    db.add(sched)
                    db.commit()
                    db.refresh(sched)
                    resolved_schedule_id = sched.id

            # Create SendJob record
            now = datetime.now(timezone.utc)
            send_job = SendJob(
                schedule_id=resolved_schedule_id,
                scheduled_start=now,
                actual_start=now,
                status="running",
            )
            db.add(send_job)
            db.commit()
            db.refresh(send_job)

            # Run the diode send in a thread (blocking I/O)
            bg_task.progress = 0.1
            success = await asyncio.to_thread(
                _execute_send, duration, bg_task,
            )

            # Update SendJob
            end_time = datetime.now(timezone.utc)
            send_job.actual_end = end_time
            send_job.duration = int((end_time - now).total_seconds())
            send_job.status = "completed" if success else "failed"
            db.commit()

            return {
                "sheet_id": sheet_id,
                "sheet_name": sheet.name,
                "item_count": item_count,
                "send_job_id": send_job.id,
                "duration_seconds": send_job.duration,
                "status": send_job.status,
            }
        finally:
            db.close()


def _execute_send(duration: float, bg_task: BackgroundTask) -> bool:
    """Run BasicDiode.send() in a thread, updating progress periodically."""
    device = get_device()
    diode = BasicDiode(device)

    # Split duration into segments for progress reporting
    segment_count = max(1, int(duration / 5))  # report every ~5 seconds
    segment_duration = duration / segment_count

    total_elapsed = 0.0
    for i in range(segment_count):
        if bg_task.is_cancelled:
            return False

        seg_dur = segment_duration
        if i == segment_count - 1:
            seg_dur = duration - total_elapsed

        success = diode.send(
            seg_dur,
            cancel=lambda: bg_task.is_cancelled,
        )
        if not success:
            return False

        total_elapsed += seg_dur
        bg_task.progress = 0.1 + 0.9 * (total_elapsed / duration)

    return True
