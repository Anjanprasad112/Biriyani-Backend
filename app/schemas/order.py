from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from app.models.enums import OrderStatus


class OrderStatusUpdate(BaseModel):

    status: OrderStatus

    reason: str | None = Field(
        default=None,
        max_length=500,
    )


class OrderRead(BaseModel):

    order_id: str

    phone_number: str

    order_type: str

    table_number: str | None = None

    total_amount: int

    cart_items: list

    status: str

    status_reason: str | None = None

    created_at: datetime

    updated_at: datetime

    paid_at: datetime | None = None

    preparation_started_at: datetime | None = None

    estimated_ready_at: datetime | None = None

    ready_at: datetime | None = None

    completed_at: datetime | None = None

    model_config = ConfigDict(
        from_attributes=True
    )