from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class TargetBase(BaseModel):
    name: str
    target_type: str | None = None
    gender: str | None = None
    date_of_birth: date | None = None
    notes: str | None = None
    active: bool = True


class TargetCreate(TargetBase):
    pass


class TargetUpdate(BaseModel):
    name: str | None = None
    target_type: str | None = None
    gender: str | None = None
    date_of_birth: date | None = None
    notes: str | None = None
    active: bool | None = None


class TargetRead(TargetBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    created_at: datetime
    updated_at: datetime
