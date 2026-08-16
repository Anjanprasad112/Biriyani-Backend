from datetime import (
    datetime,
    timedelta,
    timezone,
)

from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.order_status_history import (
    OrderStatusHistory,
)

from app.services.settings_service import (
    get_or_create_shop_settings,
)


ALLOWED_TRANSITIONS = {

    "Pending": {
        "Cancelled",
        "Rejected",
    },

    "Paid": {
        "Preparation",
        "Cancelled",
        "Rejected",
    },

    "Preparation": {
        "Ready",
        "Cancelled",
    },

    "Ready": {
        "Collected",
    },

    "Collected": set(),

    "Cancelled": set(),

    "Rejected": set(),
}


def change_order_status(
    db: Session,
    order: Order,
    new_status: str,
    user_id: int | None = None,
    reason: str | None = None,
) -> Order:

    current_status = order.status

    if new_status == current_status:
        return order

    allowed = ALLOWED_TRANSITIONS.get(
        current_status,
        set(),
    )

    if new_status not in allowed:

        raise ValueError(
            f"Cannot move order from "
            f"{current_status} to {new_status}"
        )

    if (
        new_status
        in {
            "Cancelled",
            "Rejected",
        }
        and not (
            reason
            and reason.strip()
        )
    ):

        raise ValueError(
            "A reason is required "
            f"when an order is {new_status.lower()}"
        )

    now = datetime.now(
        timezone.utc
    )

    if new_status == "Preparation":

        shop_settings = (
            get_or_create_shop_settings(
                db
            )
        )

        order.preparation_started_at = now

        order.estimated_ready_at = (
            now
            + timedelta(
                minutes=(
                    shop_settings
                    .default_preparation_minutes
                )
            )
        )

        order.status_reason = None

    elif new_status == "Ready":

        order.ready_at = now

        order.status_reason = None

    elif new_status == "Collected":

        order.completed_at = now

        order.status_reason = None

    elif new_status in {
        "Cancelled",
        "Rejected",
    }:

        order.status_reason = (
            reason.strip()
            if reason
            else None
        )

    history = OrderStatusHistory(
        order_id=order.order_id,
        old_status=current_status,
        new_status=new_status,
        reason=(
            reason.strip()
            if reason
            else None
        ),
        changed_by_user_id=user_id,
    )

    order.status = new_status

    order.updated_at = now

    db.add(
        history
    )

    db.add(
        order
    )

    db.commit()

    db.refresh(
        order
    )

    return order