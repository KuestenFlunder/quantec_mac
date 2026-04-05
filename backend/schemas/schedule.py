from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ScheduleBase(BaseModel):
    schedule_type: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    interval_duration: int | None = None
    send_duration: int | None = None
    active: bool = True
    butler_active: bool = False


class ScheduleCreate(ScheduleBase):
    pass


class ScheduleUpdate(BaseModel):
    schedule_type: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    interval_duration: int | None = None
    send_duration: int | None = None
    active: bool | None = None
    butler_active: bool | None = None


class ScheduleRead(ScheduleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    healing_sheet_id: int
    created_at: datetime


class SendJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    schedule_id: int
    scheduled_start: datetime | None = None
    actual_start: datetime | None = None
    actual_end: datetime | None = None
    duration: int | None = None
    status: str
    created_at: datetime
