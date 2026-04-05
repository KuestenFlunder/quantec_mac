from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Target(Base):
    __tablename__ = "target"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("client.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    target_type: Mapped[str | None] = mapped_column(String(50))
    gender: Mapped[str | None] = mapped_column(String(20))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    photo1: Mapped[bytes | None] = mapped_column(LargeBinary)
    photo2: Mapped[bytes | None] = mapped_column(LargeBinary)
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    client: Mapped["Client"] = relationship(back_populates="targets")
    healing_sheets: Mapped[list["HealingSheet"]] = relationship(
        back_populates="target", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Target {self.id}: {self.name}>"
