"""Hardware Diode API -- status, connect, read noise, SSE stream."""

import asyncio
import json
import time

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from hardware.ftdi import BitBangDevice

router = APIRouter()

_device: BitBangDevice | None = None
_device_url = "ftdi://ftdi:232:FTG6VIHJ/1"


def _get_device() -> BitBangDevice:
    global _device
    if _device is None:
        _device = BitBangDevice(_device_url)
    return _device


@router.get("/status")
def device_status():
    dev = _get_device()
    return {
        "connected": dev.is_open,
        "signal_quality": round(dev.signal_quality * 100, 1),
        "device_url": _device_url,
    }


@router.post("/connect")
def device_connect():
    dev = _get_device()
    if dev.is_open:
        return {"connected": True, "message": "Already connected"}
    ok = dev.open()
    return {"connected": ok, "message": "Connected" if ok else "Failed to open device"}


@router.post("/disconnect")
def device_disconnect():
    dev = _get_device()
    dev.close()
    return {"connected": False, "message": "Disconnected"}


@router.post("/read")
def read_noise(bits: int = 256, average: int = 11):
    dev = _get_device()
    if not dev.is_open:
        ok = dev.open()
        if not ok:
            return {"error": "Device not connected"}

    begin_ok = dev.begin_read(quality=True)
    if not begin_ok:
        return {"error": "Signal quality too low or no signal", "signal_quality": 0}

    raw_bits = dev.read_bits(bits, average=average)
    quality = round(dev.signal_quality * 100, 1)
    dev.end_read()

    if raw_bits is None:
        return {"error": "Failed to read bits", "signal_quality": quality}

    ones = sum(raw_bits)
    zeros = len(raw_bits) - ones
    return {
        "bits": list(raw_bits),
        "total": len(raw_bits),
        "ones": ones,
        "zeros": zeros,
        "ratio": round(ones / len(raw_bits) * 100, 1),
        "signal_quality": quality,
    }


@router.get("/stream")
async def stream_noise(request: Request):
    """Server-Sent Events endpoint streaming live noise data from the diode."""

    async def event_generator():
        dev = _get_device()
        if not dev.is_open:
            dev.open()
        if not dev.is_open:
            yield f"data: {json.dumps({'error': 'Device not connected'})}\n\n"
            return

        begin_ok = dev.begin_read(quality=True)
        if not begin_ok:
            yield f"data: {json.dumps({'error': 'Signal quality check failed'})}\n\n"
            return

        try:
            while True:
                if await request.is_disconnected():
                    break

                bits = await asyncio.to_thread(dev.read_bits, 128, 5)
                if bits is None:
                    yield f"data: {json.dumps({'error': 'Read failed'})}\n\n"
                    break

                ones = sum(bits)
                zeros = len(bits) - ones
                quality = round(dev.signal_quality * 100, 1)

                payload = json.dumps({
                    "t": round(time.time() * 1000),
                    "bits": list(bits),
                    "ones": ones,
                    "zeros": zeros,
                    "ratio": round(ones / len(bits) * 100, 1),
                    "signal_quality": quality,
                })
                yield f"data: {payload}\n\n"
                await asyncio.sleep(0.05)
        finally:
            dev.end_read()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/scan")
def run_scan(slots: int = 21, cycles: int = 88, method: str = "selection"):
    """Run a raw hardware scan using the FTDI diode (abstract slots)."""
    from hardware.diode import (
        SelectionDiode,
        QUANTEC6Diode,
        QUANTEC6DiodeWithRandom,
        DistributionDiode,
        RemainderDiode,
        DiodeOperation,
    )

    dev = _get_device()
    if not dev.is_open:
        dev.open()
    if not dev.is_open:
        return {"error": "Device not connected"}

    diode_map = {
        "selection": SelectionDiode,
        "quantec6": QUANTEC6Diode,
        "quantec6random": QUANTEC6DiodeWithRandom,
        "distribution": DistributionDiode,
        "remainder": RemainderDiode,
    }
    DiodeClass = diode_map.get(method, SelectionDiode)
    diode = DiodeClass(dev)

    data = [0] * slots
    ok = diode.scan(DiodeOperation.SINGLE_SCAN, data, cycles)

    if not ok:
        return {"error": "Scan failed", "signal_quality": dev.signal_quality * 100}

    ranked = sorted(enumerate(data), key=lambda x: x[1], reverse=True)

    return {
        "slots": data,
        "ranked": [{"index": idx, "value": val} for idx, val in ranked],
        "total_cycles": cycles,
        "method": method,
        "signal_quality": round(dev.signal_quality * 100, 1),
    }


@router.post("/scan/categories")
def scan_categories(
    theme_id: int | None = None,
    cycles: int = 88,
    top_n: int = 10,
    method: str = "selection",
):
    """Stage 1: Scan over database categories to find the most relevant ones.

    This is how QUANTEC selects from 117K+ items: first narrow down categories,
    then scan items within those categories.
    """
    from hardware.diode import SelectionDiode, QUANTEC6Diode, QUANTEC6DiodeWithRandom, DistributionDiode, RemainderDiode, DiodeOperation
    from database import SessionLocal, existing_metadata
    from sqlalchemy import select

    db = SessionLocal()
    try:
        category = existing_metadata.tables.get("category")
        theme = existing_metadata.tables.get("theme")
        if category is None or theme is None:
            return {"error": "Database tables not reflected"}

        stmt = select(
            category.c.id, category.c.name, category.c.item_count,
            theme.c.name.label("theme_name"),
        ).outerjoin(theme, category.c.theme_id == theme.c.id)

        if theme_id is not None:
            stmt = stmt.where(category.c.theme_id == theme_id)

        stmt = stmt.where(category.c.item_count > 0).order_by(category.c.id)
        rows = db.execute(stmt).mappings().all()
    finally:
        db.close()

    if not rows:
        return {"error": "No categories found"}

    n = len(rows)
    dev = _get_device()
    if not dev.is_open:
        dev.open()
    if not dev.is_open:
        return {"error": "Device not connected"}

    diode_map = {
        "selection": SelectionDiode, "quantec6": QUANTEC6Diode,
        "quantec6random": QUANTEC6DiodeWithRandom,
        "distribution": DistributionDiode, "remainder": RemainderDiode,
    }
    DiodeClass = diode_map.get(method, SelectionDiode)
    diode = DiodeClass(dev)

    data = [0] * n
    ok = diode.scan(DiodeOperation.SINGLE_SCAN, data, cycles)
    if not ok:
        return {"error": "Scan failed"}

    results = []
    for i, row in enumerate(rows):
        results.append({
            "category_id": row["id"],
            "category_name": row["name"],
            "theme_name": row["theme_name"],
            "item_count": row["item_count"],
            "score": data[i],
        })

    results.sort(key=lambda x: x["score"], reverse=True)

    return {
        "total_categories": n,
        "top_n": top_n,
        "results": results[:top_n],
        "all_scores": data,
        "cycles": cycles,
        "method": method,
        "signal_quality": round(dev.signal_quality * 100, 1),
    }


@router.post("/scan/items")
def scan_items(
    category_ids: str,
    cycles: int = 88,
    top_n: int = 21,
    method: str = "selection",
):
    """Stage 2: Scan items within selected categories.

    category_ids: comma-separated list of category IDs (e.g. "22,54,8")
    Returns the top-N items ranked by diode score.
    """
    from hardware.diode import SelectionDiode, QUANTEC6Diode, QUANTEC6DiodeWithRandom, DistributionDiode, RemainderDiode, DiodeOperation
    from database import SessionLocal, existing_metadata
    from sqlalchemy import select

    cat_ids = [int(c.strip()) for c in category_ids.split(",") if c.strip()]
    if not cat_ids:
        return {"error": "No category IDs provided"}

    db = SessionLocal()
    try:
        esoteric_item = existing_metadata.tables.get("esoteric_item")
        if esoteric_item is None:
            return {"error": "esoteric_item table not reflected"}

        stmt = (
            select(
                esoteric_item.c.id,
                esoteric_item.c.category_id,
                esoteric_item.c.category_name,
                esoteric_item.c.text_primary,
                esoteric_item.c.text_secondary,
            )
            .where(esoteric_item.c.category_id.in_(cat_ids))
            .order_by(esoteric_item.c.id)
        )
        rows = db.execute(stmt).mappings().all()
    finally:
        db.close()

    if not rows:
        return {"error": "No items found in selected categories"}

    n = len(rows)
    dev = _get_device()
    if not dev.is_open:
        dev.open()
    if not dev.is_open:
        return {"error": "Device not connected"}

    diode_map = {
        "selection": SelectionDiode, "quantec6": QUANTEC6Diode,
        "quantec6random": QUANTEC6DiodeWithRandom,
        "distribution": DistributionDiode, "remainder": RemainderDiode,
    }
    DiodeClass = diode_map.get(method, SelectionDiode)
    diode = DiodeClass(dev)

    data = [0] * n
    ok = diode.scan(DiodeOperation.SINGLE_SCAN, data, cycles)
    if not ok:
        return {"error": "Scan failed"}

    results = []
    for i, row in enumerate(rows):
        results.append({
            "item_id": row["id"],
            "category_id": row["category_id"],
            "category_name": row["category_name"],
            "text_primary": row["text_primary"],
            "text_secondary": row["text_secondary"],
            "score": data[i],
        })

    results.sort(key=lambda x: x["score"], reverse=True)

    return {
        "total_items": n,
        "top_n": top_n,
        "results": results[:top_n],
        "cycles": cycles,
        "method": method,
        "signal_quality": round(dev.signal_quality * 100, 1),
    }


@router.post("/scan/full")
def scan_full(
    theme_id: int | None = None,
    category_cycles: int = 88,
    item_cycles: int = 88,
    top_categories: int = 5,
    top_items: int = 21,
    method: str = "selection",
):
    """Full 2-stage QUANTEC scan: categories first, then items.

    Stage 1: Scan all categories (or within a theme) → top N categories
    Stage 2: Scan all items within top categories → top N items
    """
    cat_result = scan_categories(
        theme_id=theme_id, cycles=category_cycles,
        top_n=top_categories, method=method,
    )
    if "error" in cat_result:
        return cat_result

    winning_cat_ids = [r["category_id"] for r in cat_result["results"]]

    item_result = scan_items(
        category_ids=",".join(str(c) for c in winning_cat_ids),
        cycles=item_cycles, top_n=top_items, method=method,
    )
    if "error" in item_result:
        return item_result

    return {
        "stage1_categories": cat_result["results"],
        "stage2_items": item_result["results"],
        "total_categories_scanned": cat_result["total_categories"],
        "total_items_scanned": item_result["total_items"],
        "method": method,
        "signal_quality": item_result["signal_quality"],
    }
