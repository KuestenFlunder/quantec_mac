from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models.client import Client
from models.target import Target
from schemas.client import ClientCreate, ClientRead, ClientUpdate
from schemas.target import TargetCreate, TargetRead

router = APIRouter()


@router.get("", response_model=list[ClientRead])
def list_clients(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
    db: Session = Depends(get_db),
):
    stmt = select(Client).order_by(Client.last_name, Client.first_name)
    if active_only:
        stmt = stmt.where(Client.active.is_(True))
    stmt = stmt.offset(skip).limit(limit)
    return db.scalars(stmt).all()


@router.post("", response_model=ClientRead, status_code=201)
def create_client(data: ClientCreate, db: Session = Depends(get_db)):
    client = Client(**data.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.get("/{client_id}", response_model=ClientRead)
def get_client(client_id: int, db: Session = Depends(get_db)):
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.put("/{client_id}", response_model=ClientRead)
def update_client(client_id: int, data: ClientUpdate, db: Session = Depends(get_db)):
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(client, field, value)
    db.commit()
    db.refresh(client)
    return client


@router.delete("/{client_id}", status_code=204)
def delete_client(client_id: int, db: Session = Depends(get_db)):
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    db.delete(client)
    db.commit()


@router.get("/{client_id}/targets", response_model=list[TargetRead])
def list_client_targets(client_id: int, db: Session = Depends(get_db)):
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    stmt = select(Target).where(Target.client_id == client_id).order_by(Target.name)
    return db.scalars(stmt).all()


@router.post("/{client_id}/targets", response_model=TargetRead, status_code=201)
def create_client_target(client_id: int, data: TargetCreate, db: Session = Depends(get_db)):
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    target = Target(client_id=client_id, **data.model_dump())
    db.add(target)
    db.commit()
    db.refresh(target)
    return target
