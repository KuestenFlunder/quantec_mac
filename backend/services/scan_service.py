"""Scan service -- orchestrates morphic field scanning via the diode hardware.

Flow:
  1. Load esoteric_items for selected category_ids from pgvector DB
  2. Build data[] array (one slot per item)
  3. Run diode.scan(data, cycles) using the selected DiodeType
  4. Sort by score, return top-N results
  5. Optionally accept results into a HealingSheet
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from database import SessionLocal, existing_metadata
from hardware import (
    BasicDiode,
    DistributionDiode,
    MockDevice,
    QUANTEC6Diode,
    QUANTEC6DiodeWithRandom,
    RemainderDiode,
    SelectionDiode,
)
from hardware.diode import DiodeOperation, DiodeType
from hardware.ftdi import DeviceInterface
from models.healing_sheet import HealingSheet, HealingSheetItem
from services.send_service import get_device
from services.task_manager import BackgroundTask, task_manager

logger = logging.getLogger(__name__)

DEFAULT_CYCLES = 88
DEFAULT_TOP_N = 21


def _make_diode(diode_type: DiodeType, device: DeviceInterface) -> BasicDiode:
    """Create the appropriate diode instance for the given type."""
    mapping = {
        DiodeType.SELECTION: SelectionDiode,
        DiodeType.QUANTEC6: QUANTEC6Diode,
        DiodeType.QUANTEC6_WITH_RANDOM: QUANTEC6DiodeWithRandom,
        DiodeType.DISTRIBUTION: DistributionDiode,
        DiodeType.REMAINDER: RemainderDiode,
    }
    cls = mapping.get(diode_type, SelectionDiode)
    return cls(device=device)


def _load_items_for_categories(
    db: Session, category_ids: list[int]
) -> list[dict[str, Any]]:
    """Load esoteric_items from the vector DB for given categories."""
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
    rows = db.execute(stmt).mappings().all()
    return [dict(row) for row in rows]


class ScanService:
    """Service for running diode scans against morphic field items."""

    @staticmethod
    async def start_scan(
        category_ids: list[int],
        cycles: int = DEFAULT_CYCLES,
        diode_type: str = "selection",
        top_n: int = DEFAULT_TOP_N,
    ) -> BackgroundTask:
        """Start a background scan operation.

        Must be called from an async context.

        Args:
            category_ids: Categories to scan items from.
            cycles: Number of scan cycles (default 88).
            diode_type: One of selection, quantec6, quantec6_with_random,
                        distribution, remainder.
            top_n: Return top N results.

        Returns:
            BackgroundTask handle for status polling.
        """
        dtype = _resolve_diode_type(diode_type)
        return await task_manager.submit(
            "scan",
            ScanService._scan_coro,
            category_ids=category_ids,
            cycles=cycles,
            diode_type=dtype,
            top_n=top_n,
        )

    @staticmethod
    async def _scan_coro(
        bg_task: BackgroundTask,
        *,
        category_ids: list[int],
        cycles: int,
        diode_type: DiodeType,
        top_n: int,
    ) -> dict:
        """Async coroutine that performs the scan in a thread."""
        db: Session = SessionLocal()
        try:
            # Step 1: Load items from vector DB
            bg_task.progress = 0.05
            items = _load_items_for_categories(db, category_ids)
            if not items:
                raise ValueError(
                    f"No items found for categories: {category_ids}"
                )

            item_count = len(items)
            logger.info(
                "Scan: %d items from %d categories, %d cycles, diode=%s",
                item_count, len(category_ids), cycles, diode_type.name,
            )

            # Step 2: Run the diode scan in a thread
            bg_task.progress = 0.1

            data = await asyncio.to_thread(
                _execute_scan,
                item_count,
                cycles,
                diode_type,
                bg_task,
            )

            if data is None:
                raise RuntimeError("Scan failed -- device error or cancellation")

            # Step 3: Combine scores with items and sort
            bg_task.progress = 0.95
            scored_items = []
            max_score = max(data) if data else 1
            for idx, item in enumerate(items):
                raw_score = data[idx] if idx < len(data) else 0
                normalized = round(raw_score / max_score * 100, 1) if max_score > 0 else 0.0
                scored_items.append({
                    "rank": 0,
                    "raw_score": raw_score,
                    "score": normalized,
                    "item_id": item["id"],
                    "category_id": item["category_id"],
                    "category_name": item["category_name"],
                    "text_primary": item["text_primary"],
                    "text_secondary": item["text_secondary"],
                    "quality_score": item["quality_score"],
                })

            scored_items.sort(key=lambda x: x["raw_score"], reverse=True)
            for i, item in enumerate(scored_items):
                item["rank"] = i + 1

            top_results = scored_items[:top_n]

            return {
                "total_items": item_count,
                "cycles": cycles,
                "diode_type": diode_type.name,
                "category_ids": category_ids,
                "top_n": top_n,
                "results": top_results,
            }
        finally:
            db.close()

    @staticmethod
    def accept_results(
        healing_sheet_id: int,
        item_ids: list[int],
    ) -> dict:
        """Accept scan results into a HealingSheet.

        Creates HealingSheetItem entries for the selected morphic field items.
        """
        db: Session = SessionLocal()
        try:
            sheet = db.get(HealingSheet, healing_sheet_id)
            if sheet is None:
                raise ValueError(f"HealingSheet {healing_sheet_id} not found")

            esoteric_item = existing_metadata.tables.get("esoteric_item")
            if esoteric_item is None:
                raise RuntimeError("esoteric_item table not reflected")

            stmt = (
                select(
                    esoteric_item.c.id,
                    esoteric_item.c.text_primary,
                    esoteric_item.c.category_name,
                )
                .where(esoteric_item.c.id.in_(item_ids))
            )
            rows = {row["id"]: row for row in db.execute(stmt).mappings().all()}

            existing_max = 0
            if sheet.items:
                existing_max = max(item.sort_index for item in sheet.items)

            added = []
            for i, item_id in enumerate(item_ids):
                row = rows.get(item_id)
                if row is None:
                    continue

                hs_item = HealingSheetItem(
                    healing_sheet_id=healing_sheet_id,
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
                "healing_sheet_id": healing_sheet_id,
                "healing_sheet_name": sheet.name,
                "items_added": len(added),
                "items": added,
            }
        finally:
            db.close()


def _execute_scan(
    item_count: int,
    cycles: int,
    diode_type: DiodeType,
    bg_task: BackgroundTask,
) -> list[int] | None:
    """Run the diode scan in a blocking thread."""
    device = get_device()
    diode = _make_diode(diode_type, device)

    data = [0] * item_count

    operation = DiodeOperation.SINGLE_SCAN

    success = diode.scan(
        operation=operation,
        data=data,
        cycles=cycles,
        cancel=lambda: bg_task.is_cancelled,
    )

    if not success:
        return None

    bg_task.progress = 0.9
    return data


def _resolve_diode_type(name: str) -> DiodeType:
    """Resolve diode type from string name."""
    mapping = {
        "selection": DiodeType.SELECTION,
        "quantec6": DiodeType.QUANTEC6,
        "quantec6_with_random": DiodeType.QUANTEC6_WITH_RANDOM,
        "distribution": DiodeType.DISTRIBUTION,
        "remainder": DiodeType.REMAINDER,
    }
    result = mapping.get(name.lower())
    if result is None:
        raise ValueError(f"Unknown diode type: {name}. Valid: {list(mapping.keys())}")
    return result
