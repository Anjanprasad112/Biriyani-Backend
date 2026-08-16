from datetime import time

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class ShopSettingsUpdate(BaseModel):

    accepting_orders: bool | None = None

    default_preparation_minutes: int | None = Field(
        default=None,
        ge=1,
        le=240,
    )

    warning_active_orders: int | None = Field(
        default=None,
        ge=0,
    )

    max_active_orders: int | None = Field(
        default=None,
        ge=1,
    )

    opening_time: time | None = None

    closing_time: time | None = None


class ShopSettingsRead(BaseModel):

    shop_id: int

    accepting_orders: bool

    default_preparation_minutes: int

    warning_active_orders: int

    max_active_orders: int

    opening_time: time | None = None

    closing_time: time | None = None

    model_config = ConfigDict(
        from_attributes=True
    )


class CapacityRead(BaseModel):

    active_orders: int

    warning_active_orders: int

    max_active_orders: int

    accepting_orders: bool

    level: str