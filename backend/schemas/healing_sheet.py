from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class HealingSheetBase(BaseModel):
    name: str
    send_type: str | None = None
    sort_order: int = 0
    use_hs_picture: bool = False
    use_target_picture: bool = False
    has_advice: bool = False
    advice_text: str | None = None
    is_template: bool = False
    active: bool = True
    expiry_date: date | None = None


class HealingSheetCreate(HealingSheetBase):
    pass


class HealingSheetUpdate(BaseModel):
    name: str | None = None
    send_type: str | None = None
    sort_order: int | None = None
    use_hs_picture: bool | None = None
    use_target_picture: bool | None = None
    has_advice: bool | None = None
    advice_text: str | None = None
    is_template: bool | None = None
    active: bool | None = None
    expiry_date: date | None = None


class HealingSheetRead(HealingSheetBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    target_id: int
    created_at: datetime
    updated_at: datetime


class HealingSheetItemBase(BaseModel):
    sort_index: int = 0
    text: str | None = None
    comment: str | None = None
    potency_kind: str | None = None
    potency_value: str | None = None
    potency_intensity: float | None = None
    qrs_factor: float | None = None
    color: str | None = None
    suppress_printing: bool = False
    ignore_on_check: bool = False
    do_not_extend: bool = False
    mistake_count: int = 0
    changed_by_butler: bool = False
    morphic_field_item_id: int | None = None


class HealingSheetItemCreate(HealingSheetItemBase):
    pass


class HealingSheetItemRead(HealingSheetItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    healing_sheet_id: int
    created_at: datetime
