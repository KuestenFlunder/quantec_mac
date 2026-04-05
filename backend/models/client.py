from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Client(Base):
    __tablename__ = "client"

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    title: Mapped[str | None] = mapped_column(String(50))
    salutation: Mapped[str | None] = mapped_column(String(50))
    letter_salutation: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(200))
    phone_home: Mapped[str | None] = mapped_column(String(50))
    phone_business: Mapped[str | None] = mapped_column(String(50))
    phone_mobile: Mapped[str | None] = mapped_column(String(50))
    address_street: Mapped[str | None] = mapped_column(String(200))
    address_zip: Mapped[str | None] = mapped_column(String(20))
    address_city: Mapped[str | None] = mapped_column(String(100))
    address_country: Mapped[str | None] = mapped_column(String(100))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(20))
    photo: Mapped[bytes | None] = mapped_column(LargeBinary)
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    targets: Mapped[list["Target"]] = relationship(back_populates="client", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Client {self.id}: {self.first_name} {self.last_name}>"
