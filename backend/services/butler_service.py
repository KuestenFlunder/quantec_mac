"""Butler service -- automated sheet management.

The Butler checks for expiring HealingSheets, extends them by replacing
items that have reached their limit, and manages scheduled re-scans.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from database import SessionLocal, existing_metadata
from hardware import MockDevice, SelectionDiode, DiodeOperation
from hardware.ftdi import DeviceInterface
from models.healing_sheet import HealingSheet, HealingSheetItem
from services.task_manager import BackgroundTask, task_manager

logger = logging.getLogger(__name__)

# How many days before expiry the Butler should act
EXPIRY_WARNING_DAYS = 3
# Default extension period in days
DEFAULT_EXTENSION_DAYS = 30
# Scan cycles for replacement item selection
BUTLER_SCAN_CYCLES = 5


class ButlerService:
    """Automated HealingSheet maintenance service."""

    @staticmethod
    async def check_expiring_sheets(days_ahead: int = EXPIRY_WARNING_DAYS) -> BackgroundTask:
        """Start a background check for sheets expiring within `days_ahead` days.

        Must be called from an async context.
        Returns a BackgroundTask whose result is a list of expiring sheet summaries.
        """
        return await task_manager.submit(
            "butler_check",
            ButlerService._check_coro,
            days_ahead=days_ahead,
        )

    @staticmethod
    async def _check_coro(bg_task: BackgroundTask, *, days_ahead: int) -> list[dict]:
        db: Session = SessionLocal()
        try:
            cutoff = date.today() + timedelta(days=days_ahead)
            stmt = (
                select(HealingSheet)
                .options(joinedload(HealingSheet.items))
                .where(
                    HealingSheet.active.is_(True),
                    HealingSheet.expiry_date.isnot(None),
                    HealingSheet.expiry_date <= cutoff,
                )
                .order_by(HealingSheet.expiry_date)
            )
            sheets = db.scalars(stmt).unique().all()

            bg_task.progress = 0.5

            results = []
            for sheet in sheets:
                extendable_items = [
                    item for item in sheet.items
                    if not item.do_not_extend
                ]
                results.append({
                    "sheet_id": sheet.id,
                    "sheet_name": sheet.name,
                    "target_id": sheet.target_id,
                    "expiry_date": sheet.expiry_date.isoformat(),
                    "days_until_expiry": (sheet.expiry_date - date.today()).days,
                    "total_items": len(sheet.items),
                    "extendable_items": len(extendable_items),
                })

            bg_task.progress = 1.0
            return results
        finally:
            db.close()

    @staticmethod
    async def extend_sheet(
        sheet_id: int,
        extension_days: int = DEFAULT_EXTENSION_DAYS,
        device: DeviceInterface | None = None,
    ) -> BackgroundTask:
        """Extend a HealingSheet by running a new scan and replacing expired items.

        Must be called from an async context.

        The process:
        1. Load the sheet and its items.
        2. Find items eligible for replacement (do_not_extend=False, mistake_count > 0).
        3. Run a diode scan to select replacement items from the same categories.
        4. Swap out old items, reset counters, extend expiry_date.

        Args:
            sheet_id: The HealingSheet to extend.
            extension_days: Days to add to the expiry date.
            device: Optional device override (uses MockDevice if None).

        Returns:
            BackgroundTask handle.
        """
        return await task_manager.submit(
            "butler_extend",
            ButlerService._extend_coro,
            sheet_id=sheet_id,
            extension_days=extension_days,
            device=device,
        )

    @staticmethod
    async def _extend_coro(
        bg_task: BackgroundTask,
        *,
        sheet_id: int,
        extension_days: int,
        device: DeviceInterface | None,
    ) -> dict:
        db: Session = SessionLocal()
        try:
            # Load sheet with items
            stmt = (
                select(HealingSheet)
                .options(joinedload(HealingSheet.items))
                .where(HealingSheet.id == sheet_id)
            )
            sheet = db.scalars(stmt).unique().one_or_none()
            if sheet is None:
                raise ValueError(f"HealingSheet {sheet_id} not found")

            # Find items eligible for replacement
            replaceable = [
                item for item in sheet.items
                if not item.do_not_extend and item.mistake_count > 0
            ]

            if not replaceable:
                # Nothing to replace -- just extend the date
                sheet.expiry_date = date.today() + timedelta(days=extension_days)
                db.commit()
                return {
                    "sheet_id": sheet_id,
                    "items_replaced": 0,
                    "new_expiry_date": sheet.expiry_date.isoformat(),
                    "message": "No items needed replacement, date extended",
                }

            bg_task.progress = 0.2

            # Run scan to get selection indices for replacement
            replaced_count = await asyncio.to_thread(
                _perform_butler_scan_and_replace,
                db, sheet, replaceable, device, bg_task,
            )

            bg_task.progress = 0.9

            # Extend expiry date
            base_date = sheet.expiry_date if sheet.expiry_date and sheet.expiry_date >= date.today() else date.today()
            sheet.expiry_date = base_date + timedelta(days=extension_days)
            db.commit()

            return {
                "sheet_id": sheet_id,
                "items_replaced": replaced_count,
                "new_expiry_date": sheet.expiry_date.isoformat(),
                "total_items": len(sheet.items),
            }
        finally:
            db.close()


def _perform_butler_scan_and_replace(
    db: Session,
    sheet: HealingSheet,
    replaceable: list[HealingSheetItem],
    device: DeviceInterface | None,
    bg_task: BackgroundTask,
) -> int:
    """Run a diode scan and replace items. Executed in a thread."""
    # Use MockDevice if no real device provided
    if device is None:
        device = MockDevice()
        device.open()

    diode = SelectionDiode(device)

    replaced_count = 0
    esoteric_item_table = existing_metadata.tables.get("esoteric_item")

    for idx, item in enumerate(replaceable):
        if bg_task.is_cancelled:
            break

        # Get candidate items from the same category
        if esoteric_item_table is None or item.morphic_field_item_id is None:
            continue

        # Look up the category of the current item
        cat_stmt = select(
            esoteric_item_table.c.category_id
        ).where(
            esoteric_item_table.c.id == item.morphic_field_item_id
        )
        cat_row = db.execute(cat_stmt).first()
        if cat_row is None:
            continue

        category_id = cat_row[0]

        # Get all items in this category (excluding the current one)
        candidates_stmt = (
            select(
                esoteric_item_table.c.id,
                esoteric_item_table.c.text_primary,
            )
            .where(
                esoteric_item_table.c.category_id == category_id,
                esoteric_item_table.c.id != item.morphic_field_item_id,
            )
        )
        candidates = db.execute(candidates_stmt).all()
        if not candidates:
            continue

        # Run diode scan to select a replacement
        n = len(candidates)
        data = [0] * n
        scan_ok = diode.scan(
            DiodeOperation.SINGLE_SCAN,
            data,
            cycles=BUTLER_SCAN_CYCLES,
            cancel=lambda: bg_task.is_cancelled,
        )
        if not scan_ok or bg_task.is_cancelled:
            break

        # Pick the candidate with the highest scan value
        max_idx = max(range(n), key=lambda i: data[i])
        selected = candidates[max_idx]

        # Replace the item
        item.morphic_field_item_id = selected[0]
        item.text = selected[1] or item.text
        item.mistake_count = 0
        item.changed_by_butler = True

        replaced_count += 1
        bg_task.progress = 0.2 + 0.7 * ((idx + 1) / len(replaceable))

    db.commit()
    return replaced_count
