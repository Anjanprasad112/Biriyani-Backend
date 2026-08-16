from sqlalchemy import (
    func,
    select,
)

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import (
    ACTIVE_ORDER_STATUSES,
)

from app.models.order import Order
from app.models.shop import Shop
from app.models.shop_settings import (
    ShopSettings,
)


def get_or_create_shop_settings(
    db: Session,
    shop_id: int | None = None,
) -> ShopSettings:

    if shop_id is None:
        shop_id = settings.default_shop_id

    shop_settings = db.get(
        ShopSettings,
        shop_id,
    )

    if shop_settings:
        return shop_settings

    shop = db.get(
        Shop,
        shop_id,
    )

    if not shop:

        shop = Shop(
            id=shop_id,
            name="Watave's Biryani",
            timezone=settings.app_timezone,
            is_active=True,
        )

        db.add(shop)

        db.flush()

    shop_settings = ShopSettings(
        shop_id=shop_id,
        accepting_orders=True,
        default_preparation_minutes=20,
        warning_active_orders=30,
        max_active_orders=40,
    )

    db.add(shop_settings)

    db.commit()

    db.refresh(
        shop_settings
    )

    return shop_settings


def get_active_order_count(
    db: Session,
) -> int:

    count = db.scalar(
        select(
            func.count(
                Order.order_id
            )
        ).where(
            Order.status.in_(
                ACTIVE_ORDER_STATUSES
            )
        )
    )

    return int(
        count or 0
    )


def get_capacity(
    db: Session,
    shop_id: int | None = None,
) -> dict:

    shop_settings = (
        get_or_create_shop_settings(
            db=db,
            shop_id=shop_id,
        )
    )

    active_orders = (
        get_active_order_count(
            db
        )
    )

    if (
        active_orders
        >= shop_settings.max_active_orders
    ):

        level = "FULL"

    elif (
        active_orders
        >= shop_settings.warning_active_orders
    ):

        level = "WARNING"

    else:

        level = "NORMAL"

    return {
        "active_orders":
            active_orders,

        "warning_active_orders":
            shop_settings.warning_active_orders,

        "max_active_orders":
            shop_settings.max_active_orders,

        "accepting_orders":
            shop_settings.accepting_orders,

        "level":
            level,
    }