from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Schedule(Base):
    __tablename__ = "schedule"

    id: Mapped[int] = mapped_column(primary_key=True)
    healing_sheet_id: Mapped[int] = mapped_column(ForeignKey("healing_sheet.id", ondelete="CASCADE"))
    schedule_type: Mapped[str | None] = mapped_column(String(50))
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    interval_duration: Mapped[int | None] = mapped_column(Integer)
    send_duration: Mapped[int | None] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    butler_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    healing_sheet: Mapped["HealingSheet"] = relationship(back_populates="schedules")
    send_jobs: Mapped[list["SendJob"]] = relationship(
        back_populates="schedule", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Schedule {self.id}: {self.schedule_type}>"


class SendJob(Base):
    __tablename__ = "send_job"

    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("schedule.id", ondelete="CASCADE"))
    scheduled_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    schedule: Mapped["Schedule"] = relationship(back_populates="send_jobs")

    def __repr__(self) -> str:
        return f"<SendJob {self.id}: {self.status}>"
