"""Send API -- diode sending endpoints using threading.Thread.

Endpoints:
  POST /api/send/direct     -- start send {healing_sheet_id, duration_seconds}
  GET  /api/send/status      -- {status, elapsed, total_duration, healing_sheet_name}
  POST /api/send/stop        -- cancel running send
  GET  /api/send/schedules/{id}
  PUT  /api/send/schedules/{id}
  DELETE /api/send/schedules/{id}
  GET  /api/send/schedules/{id}/jobs
  POST /api/send/butler/check
  POST /api/send/butler/extend/{id}
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from database import SessionLocal, get_db
from hardware import BasicDiode
from models.healing_sheet import HealingSheet
from models.schedule import Schedule, SendJob
from schemas.schedule import ScheduleRead, ScheduleUpdate, SendJobRead
from services.butler_service import ButlerService
from services.send_service import get_device

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Global send state ───────────────────────────────────────────

_send_state: dict[str, Any] = {
    "status": "idle",              # idle | running | completed | error
    "progress": 0.0,               # 0.0 .. 1.0
    "error": None,
    "healing_sheet_id": None,
    "healing_sheet_name": None,
    "duration_seconds": 0,
    "elapsed_seconds": 0.0,
    "cancel": False,
    "send_job_id": None,
}
_send_lock = threading.Lock()
_send_thread: threading.Thread | None = None


# ── Request/Response Schemas ────────────────────────────────────

class SendDirectRequest(BaseModel):
    healing_sheet_id: int
    duration_seconds: int = 120


class SendStatusResponse(BaseModel):
    status: str = "idle"
    progress: float = 0.0
    elapsed_seconds: float = 0.0
    total_duration: int = 0
    healing_sheet_id: int | None = None
    healing_sheet_name: str | None = None
    send_job_id: int | None = None
    error: str | None = None
    device_connected: bool = False
    signal_quality: float = 0.0


class ButlerExtendRequest(BaseModel):
    extension_days: int = 30


# ── Send Control ────────────────────────────────────────────────

@router.post("/direct")
def start_direct_send(req: SendDirectRequest):
    """Start sending a HealingSheet through the diode in a background thread."""
    global _send_thread

    with _send_lock:
        if _send_state["status"] == "running":
            raise HTTPException(status_code=409, detail="Send already running")

        _send_state["status"] = "running"
        _send_state["progress"] = 0.0
        _send_state["error"] = None
        _send_state["cancel"] = False
        _send_state["elapsed_seconds"] = 0.0
        _send_state["healing_sheet_id"] = req.healing_sheet_id
        _send_state["healing_sheet_name"] = None
        _send_state["duration_seconds"] = req.duration_seconds
        _send_state["send_job_id"] = None

    _send_thread = threading.Thread(
        target=_run_send,
        args=(req.healing_sheet_id, req.duration_seconds),
        daemon=True,
    )
    _send_thread.start()

    return {
        "status": "running",
        "healing_sheet_id": req.healing_sheet_id,
        "duration_seconds": req.duration_seconds,
    }


@router.get("/status", response_model=SendStatusResponse)
def get_send_status():
    """Get current send operation status."""
    device_connected = False
    signal_quality = 0.0
    try:
        dev = get_device()
        device_connected = dev.is_open
        signal_quality = dev.signal_quality
    except Exception:
        pass

    with _send_lock:
        return SendStatusResponse(
            status=_send_state["status"],
            progress=_send_state["progress"],
            elapsed_seconds=_send_state["elapsed_seconds"],
            total_duration=_send_state["duration_seconds"],
            healing_sheet_id=_send_state["healing_sheet_id"],
            healing_sheet_name=_send_state["healing_sheet_name"],
            send_job_id=_send_state["send_job_id"],
            error=_send_state["error"],
            device_connected=device_connected,
            signal_quality=signal_quality,
        )


@router.post("/stop")
def stop_send():
    """Stop the currently running send operation."""
    with _send_lock:
        if _send_state["status"] != "running":
            raise HTTPException(status_code=400, detail="No send running")
        _send_state["cancel"] = True
    return {"status": "cancelling"}


# ── Background send thread ──────────────────────────────────────

def _run_send(healing_sheet_id: int, duration_seconds: int) -> None:
    """Background thread: load sheet, run diode.send(), record SendJob."""
    db: Session = SessionLocal()
    try:
        # Load the HealingSheet
        stmt = (
            select(HealingSheet)
            .options(joinedload(HealingSheet.items))
            .where(HealingSheet.id == healing_sheet_id)
        )
        sheet = db.scalars(stmt).unique().one_or_none()
        if sheet is None:
            raise ValueError(f"HealingSheet {healing_sheet_id} not found")

        with _send_lock:
            _send_state["healing_sheet_name"] = sheet.name
            _send_state["progress"] = 0.05

        # Find or create schedule for SendJob
        sched_stmt = (
            select(Schedule)
            .where(Schedule.healing_sheet_id == healing_sheet_id, Schedule.active.is_(True))
            .limit(1)
        )
        sched = db.scalars(sched_stmt).first()
        if sched is None:
            sched = Schedule(
                healing_sheet_id=healing_sheet_id,
                schedule_type="ad_hoc",
                active=False,
            )
            db.add(sched)
            db.commit()
            db.refresh(sched)

        # Create SendJob record
        now = datetime.now(timezone.utc)
        send_job = SendJob(
            schedule_id=sched.id,
            scheduled_start=now,
            actual_start=now,
            status="running",
        )
        db.add(send_job)
        db.commit()
        db.refresh(send_job)

        with _send_lock:
            _send_state["send_job_id"] = send_job.id
            _send_state["progress"] = 0.1

        # Run the diode send in segments for progress reporting
        device = get_device()
        diode = BasicDiode(device)

        segment_count = max(1, duration_seconds // 5)
        segment_duration = duration_seconds / segment_count
        total_elapsed = 0.0

        for i in range(segment_count):
            if _send_state["cancel"]:
                break

            seg_dur = segment_duration
            if i == segment_count - 1:
                seg_dur = duration_seconds - total_elapsed

            success = diode.send(
                seg_dur,
                cancel=lambda: _send_state["cancel"],
            )
            if not success and not _send_state["cancel"]:
                raise RuntimeError("Diode send failed")

            total_elapsed += seg_dur
            with _send_lock:
                _send_state["elapsed_seconds"] = total_elapsed
                _send_state["progress"] = 0.1 + 0.9 * (total_elapsed / duration_seconds)

            if not success:
                break

        # Update SendJob
        end_time = datetime.now(timezone.utc)
        was_cancelled = _send_state["cancel"]
        send_job.actual_end = end_time
        send_job.duration = int((end_time - now).total_seconds())
        send_job.status = "cancelled" if was_cancelled else "completed"
        db.commit()

        with _send_lock:
            _send_state["status"] = "idle" if was_cancelled else "completed"
            if not was_cancelled:
                _send_state["progress"] = 1.0

    except Exception as e:
        logger.exception("Send failed")
        with _send_lock:
            _send_state["status"] = "error"
            _send_state["error"] = str(e)
    finally:
        db.close()


# ── Schedule Management ─────────────────────────────────────────

@router.get("/schedules/{schedule_id}", response_model=ScheduleRead)
def get_schedule(schedule_id: int, db: Session = Depends(get_db)):
    schedule = db.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule


@router.put("/schedules/{schedule_id}", response_model=ScheduleRead)
def update_schedule(schedule_id: int, data: ScheduleUpdate, db: Session = Depends(get_db)):
    schedule = db.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(schedule, field, value)
    db.commit()
    db.refresh(schedule)
    return schedule


@router.delete("/schedules/{schedule_id}", status_code=204)
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    schedule = db.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    db.delete(schedule)
    db.commit()


@router.get("/schedules/{schedule_id}/jobs", response_model=list[SendJobRead])
def list_send_jobs(schedule_id: int, db: Session = Depends(get_db)):
    schedule = db.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    stmt = (
        select(SendJob)
        .where(SendJob.schedule_id == schedule_id)
        .order_by(SendJob.scheduled_start.desc())
    )
    return db.scalars(stmt).all()


# ── Butler ──────────────────────────────────────────────────────

@router.post("/butler/check")
def butler_check_expiring(days_ahead: int = Query(3, ge=1, le=90)):
    """Run the Butler check for expiring HealingSheets."""
    bg_task = ButlerService.check_expiring_sheets(days_ahead=days_ahead)
    return bg_task


@router.post("/butler/extend/{sheet_id}")
def butler_extend_sheet(sheet_id: int, req: ButlerExtendRequest | None = None):
    """Extend a HealingSheet: re-scan and replace expired items."""
    extension_days = req.extension_days if req else 30
    bg_task = ButlerService.extend_sheet(
        sheet_id=sheet_id,
        extension_days=extension_days,
    )
    return bg_task
