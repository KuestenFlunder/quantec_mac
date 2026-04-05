from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ClientBase(BaseModel):
    first_name: str
    last_name: str
    title: str | None = None
    salutation: str | None = None
    letter_salutation: str | None = None
    email: str | None = None
    phone_home: str | None = None
    phone_business: str | None = None
    phone_mobile: str | None = None
    address_street: str | None = None
    address_zip: str | None = None
    address_city: str | None = None
    address_country: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    notes: str | None = None
    active: bool = True


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    title: str | None = None
    salutation: str | None = None
    letter_salutation: str | None = None
    email: str | None = None
    phone_home: str | None = None
    phone_business: str | None = None
    phone_mobile: str | None = None
    address_street: str | None = None
    address_zip: str | None = None
    address_city: str | None = None
    address_country: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    notes: str | None = None
    active: bool | None = None


class ClientRead(ClientBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
