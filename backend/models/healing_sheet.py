from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class HealingSheet(Base):
    __tablename__ = "healing_sheet"

    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("target.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    send_type: Mapped[str | None] = mapped_column(String(50))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    use_hs_picture: Mapped[bool] = mapped_column(Boolean, default=False)
    use_target_picture: Mapped[bool] = mapped_column(Boolean, default=False)
    has_advice: Mapped[bool] = mapped_column(Boolean, default=False)
    advice_text: Mapped[str | None] = mapped_column(Text)
    is_template: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    photo: Mapped[bytes | None] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    target: Mapped["Target"] = relationship(back_populates="healing_sheets")
    items: Mapped[list["HealingSheetItem"]] = relationship(
        back_populates="healing_sheet", cascade="all, delete-orphan", order_by="HealingSheetItem.sort_index"
    )
    schedules: Mapped[list["Schedule"]] = relationship(
        back_populates="healing_sheet", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<HealingSheet {self.id}: {self.name}>"


class HealingSheetItem(Base):
    __tablename__ = "healing_sheet_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    healing_sheet_id: Mapped[int] = mapped_column(ForeignKey("healing_sheet.id", ondelete="CASCADE"))
    sort_index: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str | None] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)
    potency_kind: Mapped[str | None] = mapped_column(String(50))
    potency_value: Mapped[str | None] = mapped_column(String(50))
    potency_intensity: Mapped[float | None] = mapped_column(Float)
    qrs_factor: Mapped[float | None] = mapped_column(Float)
    color: Mapped[str | None] = mapped_column(String(20))
    media_data: Mapped[bytes | None] = mapped_column(LargeBinary)
    suppress_printing: Mapped[bool] = mapped_column(Boolean, default=False)
    ignore_on_check: Mapped[bool] = mapped_column(Boolean, default=False)
    do_not_extend: Mapped[bool] = mapped_column(Boolean, default=False)
    mistake_count: Mapped[int] = mapped_column(Integer, default=0)
    changed_by_butler: Mapped[bool] = mapped_column(Boolean, default=False)
    morphic_field_item_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("esoteric_item.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    healing_sheet: Mapped["HealingSheet"] = relationship(back_populates="items")

    def __repr__(self) -> str:
        return f"<HealingSheetItem {self.id}: {self.text}>"
