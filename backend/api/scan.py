"""Scan API -- diode scanning endpoints using threading.Thread.

Endpoints:
  POST /api/scan/start   -- start scan {category_ids, cycles, diode_type, healing_sheet_id}
  GET  /api/scan/status   -- {status, progress}
  GET  /api/scan/results  -- [{item_id, text_primary, category_name, score}]
  POST /api/scan/accept   -- {item_ids, healing_sheet_id} -> create HealingSheetItems
"""

from __future__ import annotations

import logging
import math
import threading
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import SessionLocal, existing_metadata, get_db
from hardware import (
    DistributionDiode,
    MockDevice,
    QUANTEC6Diode,
    QUANTEC6DiodeWithRandom,
    RemainderDiode,
    SelectionDiode,
)
from hardware.diode import DiodeOperation, DiodeType
from hardware.ftdi import DeviceInterface
from hardware.mock_device import MockDevice
from models.healing_sheet import HealingSheet, HealingSheetItem
from services.send_service import get_device

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Global scan state ───────────────────────────────────────────

_scan_state: dict[str, Any] = {
    "status": "idle",       # idle | running | completed | error
    "progress": 0.0,        # 0.0 .. 1.0
    "error": None,          # error message if status == "error"
    "category_ids": [],
    "cycles": 0,
    "diode_type": "",
    "total_items": 0,
    "results": [],           # sorted scored items
    "cancel": False,
}
_scan_lock = threading.Lock()
_scan_thread: threading.Thread | None = None


def _get_scan_state() -> dict[str, Any]:
    with _scan_lock:
        return {
            "status": _scan_state["status"],
            "progress": _scan_state["progress"],
            "error": _scan_state["error"],
            "category_ids": _scan_state["category_ids"],
            "cycles": _scan_state["cycles"],
            "diode_type": _scan_state["diode_type"],
            "total_items": _scan_state["total_items"],
        }


# ── Request/Response Schemas ────────────────────────────────────

class ScanStartRequest(BaseModel):
    category_ids: list[int] = Field(..., min_length=1)
    cycles: int = Field(88, ge=1, le=1000)
    diode_type: str = Field(
        "selection",
        description="selection|quantec6|quantec6_with_random|distribution|remainder",
    )
    healing_sheet_id: int | None = Field(None, description="Optional target sheet")


class ScanAcceptRequest(BaseModel):
    item_ids: list[int] = Field(..., min_length=1)
    healing_sheet_id: int


class ScanResultItem(BaseModel):
    rank: int
    raw_score: int
    score: float
    item_id: int
    category_id: int
    category_name: str
    text_primary: str | None = None
    text_secondary: str | None = None
    quality_score: float | None = None


# ── Endpoints ───────────────────────────────────────────────────

@router.post("/start")
def start_scan(req: ScanStartRequest):
    """Start a diode scan in a background thread."""
    global _scan_thread

    with _scan_lock:
        if _scan_state["status"] == "running":
            raise HTTPException(status_code=409, detail="Scan already running")

        _scan_state["status"] = "running"
        _scan_state["progress"] = 0.0
        _scan_state["error"] = None
        _scan_state["cancel"] = False
        _scan_state["results"] = []
        _scan_state["category_ids"] = req.category_ids
        _scan_state["cycles"] = req.cycles
        _scan_state["diode_type"] = req.diode_type

    _scan_thread = threading.Thread(
        target=_run_scan,
        args=(req.category_ids, req.cycles, req.diode_type),
        daemon=True,
    )
    _scan_thread.start()

    return {
        "status": "running",
        "category_ids": req.category_ids,
        "cycles": req.cycles,
        "diode_type": req.diode_type,
    }


@router.get("/status")
def get_scan_status():
    """Get current scan status and progress."""
    return _get_scan_state()


@router.get("/results", response_model=list[ScanResultItem])
def get_scan_results():
    """Get results of the most recent completed scan."""
    with _scan_lock:
        if _scan_state["status"] == "running":
            raise HTTPException(status_code=202, detail="Scan still running")
        if _scan_state["status"] == "error":
            raise HTTPException(
                status_code=500,
                detail=_scan_state["error"] or "Scan failed",
            )
        if not _scan_state["results"]:
            raise HTTPException(status_code=404, detail="No scan results available")
        return [ScanResultItem(**r) for r in _scan_state["results"]]


@router.post("/accept")
def accept_scan_results(req: ScanAcceptRequest, db: Session = Depends(get_db)):
    """Accept scan results: create HealingSheetItems from selected esoteric_items."""
    sheet = db.get(HealingSheet, req.healing_sheet_id)
    if sheet is None:
        raise HTTPException(status_code=404, detail="HealingSheet not found")

    esoteric_item = existing_metadata.tables.get("esoteric_item")
    if esoteric_item is None:
        raise HTTPException(status_code=500, detail="esoteric_item table not reflected")

    # Load selected items
    stmt = (
        select(
            esoteric_item.c.id,
            esoteric_item.c.text_primary,
            esoteric_item.c.category_name,
        )
        .where(esoteric_item.c.id.in_(req.item_ids))
    )
    rows = {row["id"]: row for row in db.execute(stmt).mappings().all()}

    # Find current max sort_index
    existing_max = 0
    if sheet.items:
        existing_max = max(item.sort_index for item in sheet.items)

    added = []
    for i, item_id in enumerate(req.item_ids):
        row = rows.get(item_id)
        if row is None:
            continue
        hs_item = HealingSheetItem(
            healing_sheet_id=req.healing_sheet_id,
            sort_index=existing_max + i + 1,
            text=row["text_primary"],
            comment=row["category_name"],
            morphic_field_item_id=item_id,
        )
        db.add(hs_item)
        added.append({
            "item_id": item_id,
            "text": row["text_primary"],
            "category": row["category_name"],
            "sort_index": hs_item.sort_index,
        })

    db.commit()

    return {
        "healing_sheet_id": req.healing_sheet_id,
        "healing_sheet_name": sheet.name,
        "items_added": len(added),
        "items": added,
    }


@router.post("/cancel")
def cancel_scan():
    """Cancel the currently running scan."""
    with _scan_lock:
        if _scan_state["status"] != "running":
            raise HTTPException(status_code=400, detail="No scan running")
        _scan_state["cancel"] = True
    return {"status": "cancelling"}


# ── Background scan thread ──────────────────────────────────────

DIODE_TYPE_MAP = {
    "selection": (DiodeType.SELECTION, SelectionDiode),
    "quantec6": (DiodeType.QUANTEC6, QUANTEC6Diode),
    "quantec6_with_random": (DiodeType.QUANTEC6_WITH_RANDOM, QUANTEC6DiodeWithRandom),
    "distribution": (DiodeType.DISTRIBUTION, DistributionDiode),
    "remainder": (DiodeType.REMAINDER, RemainderDiode),
}


def _run_scan(category_ids: list[int], cycles: int, diode_type: str) -> None:
    """Background thread: load items, run diode scan, store results."""
    db: Session = SessionLocal()
    try:
        # Step 1: Load items from vector DB
        with _scan_lock:
            _scan_state["progress"] = 0.05

        esoteric_item = existing_metadata.tables.get("esoteric_item")
        if esoteric_item is None:
            raise RuntimeError("esoteric_item table not reflected")

        stmt = (
            select(
                esoteric_item.c.id,
                esoteric_item.c.category_id,
                esoteric_item.c.category_name,
                esoteric_item.c.text_primary,
                esoteric_item.c.text_secondary,
                esoteric_item.c.quality_score,
            )
            .where(esoteric_item.c.category_id.in_(category_ids))
            .order_by(esoteric_item.c.id)
        )
        items = [dict(row) for row in db.execute(stmt).mappings().all()]

        if not items:
            raise ValueError(f"No items found for categories: {category_ids}")

        item_count = len(items)
        with _scan_lock:
            _scan_state["total_items"] = item_count
            _scan_state["progress"] = 0.1

        logger.info(
            "Scan: %d items, %d categories, %d cycles, diode=%s",
            item_count, len(category_ids), cycles, diode_type,
        )

        # Step 2: Run diode scan
        entry = DIODE_TYPE_MAP.get(diode_type.lower())
        if entry is None:
            raise ValueError(f"Unknown diode type: {diode_type}")
        _, diode_cls = entry

        device = get_device()
        diode = diode_cls(device=device)
        data = [0] * item_count

        success = diode.scan(
            operation=DiodeOperation.SINGLE_SCAN,
            data=data,
            cycles=cycles,
            cancel=lambda: _scan_state["cancel"],
        )

        if not success:
            if _scan_state["cancel"]:
                with _scan_lock:
                    _scan_state["status"] = "idle"
                    _scan_state["progress"] = 0.0
                return
            raise RuntimeError("Diode scan failed")

        # Step 3: Score and sort results
        with _scan_lock:
            _scan_state["progress"] = 0.9

        max_score = max(data) if data else 1
        scored = []
        for idx, item in enumerate(items):
            raw = data[idx] if idx < len(data) else 0
            normalized = round(raw / max_score * 100, 1) if max_score > 0 else 0.0
            scored.append({
                "rank": 0,
                "raw_score": raw,
                "score": normalized,
                "item_id": item["id"],
                "category_id": item["category_id"],
                "category_name": item["category_name"],
                "text_primary": item["text_primary"],
                "text_secondary": item["text_secondary"],
                "quality_score": item["quality_score"],
            })

        scored.sort(key=lambda x: x["raw_score"], reverse=True)
        for i, s in enumerate(scored):
            s["rank"] = i + 1

        with _scan_lock:
            _scan_state["status"] = "completed"
            _scan_state["progress"] = 1.0
            _scan_state["results"] = scored

    except Exception as e:
        logger.exception("Scan failed")
        with _scan_lock:
            _scan_state["status"] = "error"
            _scan_state["error"] = str(e)
    finally:
        db.close()
