from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models.healing_sheet import HealingSheet, HealingSheetItem
from models.schedule import Schedule
from schemas.healing_sheet import (
    HealingSheetItemCreate,
    HealingSheetItemRead,
    HealingSheetRead,
    HealingSheetUpdate,
)
from schemas.schedule import ScheduleCreate, ScheduleRead

router = APIRouter()


@router.get("", response_model=list[HealingSheetRead])
def list_all_sheets(db: Session = Depends(get_db)):
    stmt = select(HealingSheet).order_by(HealingSheet.id)
    return db.scalars(stmt).all()


@router.get("/{sheet_id}", response_model=HealingSheetRead)
def get_sheet(sheet_id: int, db: Session = Depends(get_db)):
    sheet = db.get(HealingSheet, sheet_id)
    if not sheet:
        raise HTTPException(status_code=404, detail="HealingSheet not found")
    return sheet


@router.put("/{sheet_id}", response_model=HealingSheetRead)
def update_sheet(sheet_id: int, data: HealingSheetUpdate, db: Session = Depends(get_db)):
    sheet = db.get(HealingSheet, sheet_id)
    if not sheet:
        raise HTTPException(status_code=404, detail="HealingSheet not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(sheet, field, value)
    db.commit()
    db.refresh(sheet)
    return sheet


@router.delete("/{sheet_id}", status_code=204)
def delete_sheet(sheet_id: int, db: Session = Depends(get_db)):
    sheet = db.get(HealingSheet, sheet_id)
    if not sheet:
        raise HTTPException(status_code=404, detail="HealingSheet not found")
    db.delete(sheet)
    db.commit()


@router.get("/{sheet_id}/items", response_model=list[HealingSheetItemRead])
def list_sheet_items(sheet_id: int, db: Session = Depends(get_db)):
    sheet = db.get(HealingSheet, sheet_id)
    if not sheet:
        raise HTTPException(status_code=404, detail="HealingSheet not found")
    stmt = (
        select(HealingSheetItem)
        .where(HealingSheetItem.healing_sheet_id == sheet_id)
        .order_by(HealingSheetItem.sort_index)
    )
    return db.scalars(stmt).all()


@router.post("/{sheet_id}/items", response_model=HealingSheetItemRead, status_code=201)
def create_sheet_item(sheet_id: int, data: HealingSheetItemCreate, db: Session = Depends(get_db)):
    sheet = db.get(HealingSheet, sheet_id)
    if not sheet:
        raise HTTPException(status_code=404, detail="HealingSheet not found")
    item = HealingSheetItem(healing_sheet_id=sheet_id, **data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{sheet_id}/items/{item_id}", status_code=204)
def delete_sheet_item(sheet_id: int, item_id: int, db: Session = Depends(get_db)):
    item = db.get(HealingSheetItem, item_id)
    if not item or item.healing_sheet_id != sheet_id:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()


@router.get("/{sheet_id}/schedules", response_model=list[ScheduleRead])
def list_sheet_schedules(sheet_id: int, db: Session = Depends(get_db)):
    sheet = db.get(HealingSheet, sheet_id)
    if not sheet:
        raise HTTPException(status_code=404, detail="HealingSheet not found")
    stmt = select(Schedule).where(Schedule.healing_sheet_id == sheet_id)
    return db.scalars(stmt).all()


@router.post("/{sheet_id}/schedules", response_model=ScheduleRead, status_code=201)
def create_sheet_schedule(sheet_id: int, data: ScheduleCreate, db: Session = Depends(get_db)):
    sheet = db.get(HealingSheet, sheet_id)
    if not sheet:
        raise HTTPException(status_code=404, detail="HealingSheet not found")
    schedule = Schedule(healing_sheet_id=sheet_id, **data.model_dump())
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule
