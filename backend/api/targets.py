from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models.healing_sheet import HealingSheet
from models.target import Target
from schemas.healing_sheet import HealingSheetCreate, HealingSheetRead
from schemas.target import TargetRead, TargetUpdate

router = APIRouter()


@router.get("/{target_id}", response_model=TargetRead)
def get_target(target_id: int, db: Session = Depends(get_db)):
    target = db.get(Target, target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    return target


@router.put("/{target_id}", response_model=TargetRead)
def update_target(target_id: int, data: TargetUpdate, db: Session = Depends(get_db)):
    target = db.get(Target, target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(target, field, value)
    db.commit()
    db.refresh(target)
    return target


@router.delete("/{target_id}", status_code=204)
def delete_target(target_id: int, db: Session = Depends(get_db)):
    target = db.get(Target, target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    db.delete(target)
    db.commit()


@router.get("/{target_id}/sheets", response_model=list[HealingSheetRead])
def list_target_sheets(target_id: int, db: Session = Depends(get_db)):
    target = db.get(Target, target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    stmt = (
        select(HealingSheet)
        .where(HealingSheet.target_id == target_id)
        .order_by(HealingSheet.sort_order)
    )
    return db.scalars(stmt).all()


@router.post("/{target_id}/sheets", response_model=HealingSheetRead, status_code=201)
def create_target_sheet(target_id: int, data: HealingSheetCreate, db: Session = Depends(get_db)):
    target = db.get(Target, target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    sheet = HealingSheet(target_id=target_id, **data.model_dump())
    db.add(sheet)
    db.commit()
    db.refresh(sheet)
    return sheet
