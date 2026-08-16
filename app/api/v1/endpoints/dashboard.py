from collections import defaultdict

from datetime import (
    date,
    datetime,
    time,
    timedelta,
    timezone,
)

from zoneinfo import ZoneInfo

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)

from sqlalchemy import (
    func,
    select,
)

from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
)

from app.core.config import settings

from app.db.session import get_db

from app.models.enums import (
    ACTIVE_ORDER_STATUSES,
)

from app.models.order import Order

from app.models.user import (
    StaffUser,
)

from app.schemas.dashboard import (
    DashboardSummary,
)


router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
)


REVENUE_STATUSES = {
    "Paid",
    "Preparation",
    "Ready",
    "Collected",
}


def _resolve_range(
    period: str,
    date_from: date | None,
    date_to: date | None,
):

    local_timezone = ZoneInfo(
        settings.app_timezone
    )

    today = datetime.now(
        local_timezone
    ).date()

    if (
        date_from is not None
        or date_to is not None
    ):

        if (
            date_from is None
            or date_to is None
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "Both date_from and date_to "
                    "are required"
                ),
            )

        start_date = date_from

        end_date = date_to

    elif period == "today":

        start_date = today

        end_date = today

    elif period == "7d":

        start_date = (
            today
            - timedelta(
                days=6
            )
        )

        end_date = today

    elif period == "30d":

        start_date = (
            today
            - timedelta(
                days=29
            )
        )

        end_date = today

    else:

        raise HTTPException(
            status_code=400,
            detail=(
                "period must be one of: "
                "today, 7d, 30d"
            ),
        )

    if start_date > end_date:

        raise HTTPException(
            status_code=400,
            detail=(
                "date_from cannot be "
                "after date_to"
            ),
        )

    start_local = datetime.combine(
        start_date,
        time.min,
        tzinfo=local_timezone,
    )

    end_local = datetime.combine(
        end_date
        + timedelta(days=1),
        time.min,
        tzinfo=local_timezone,
    )

    return (
        start_date,
        end_date,
        start_local.astimezone(
            timezone.utc
        ),
        end_local.astimezone(
            timezone.utc
        ),
        local_timezone,
    )


@router.get(
    "/summary",
    response_model=DashboardSummary,
)
def dashboard_summary(
    period: str = Query(
        default="today"
    ),
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(
        get_db
    ),
    current_user: StaffUser = Depends(
        get_current_user
    ),
):

    (
        start_date,
        end_date,
        start_utc,
        end_utc,
        local_timezone,
    ) = _resolve_range(
        period,
        date_from,
        date_to,
    )

    order_date = func.coalesce(
        Order.paid_at,
        Order.created_at,
    )

    orders = db.scalars(
        select(
            Order
        ).where(
            order_date >= start_utc,
            order_date < end_utc,
            Order.status != "Pending",
        )
    ).all()

    active_orders = db.scalar(
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

    revenue_orders = [
        order
        for order in orders
        if order.status
        in REVENUE_STATUSES
    ]

    total_revenue = sum(
        int(
            order.total_amount
            or 0
        )
        for order
        in revenue_orders
    )

    total_orders = len(
        orders
    )

    completed_orders = sum(
        1
        for order in orders
        if order.status
        == "Collected"
    )

    cancelled_orders = sum(
        1
        for order in orders
        if order.status
        == "Cancelled"
    )

    rejected_orders = sum(
        1
        for order in orders
        if order.status
        == "Rejected"
    )

    average_order_value = (
        int(
            total_revenue
            / len(
                revenue_orders
            )
        )
        if revenue_orders
        else 0
    )

    preparation_minutes = []

    for order in orders:

        if (
            order.preparation_started_at
            and order.ready_at
        ):

            seconds = (
                order.ready_at
                - order.preparation_started_at
            ).total_seconds()

            if seconds >= 0:

                preparation_minutes.append(
                    seconds / 60
                )

    average_preparation_minutes = (
        int(
            sum(
                preparation_minutes
            )
            / len(
                preparation_minutes
            )
        )
        if preparation_minutes
        else 0
    )

    sales_map = {}

    current_date = start_date

    while (
        current_date
        <= end_date
    ):

        sales_map[
            current_date
        ] = {
            "revenue": 0,
            "orders": 0,
        }

        current_date += timedelta(
            days=1
        )

    item_totals = defaultdict(
        lambda: {
            "quantity": 0,
            "revenue": 0,
        }
    )

    for order in revenue_orders:

        timestamp = (
            order.paid_at
            or order.created_at
        )

        local_date = (
            timestamp
            .astimezone(
                local_timezone
            )
            .date()
        )

        if local_date in sales_map:

            sales_map[
                local_date
            ]["revenue"] += int(
                order.total_amount
                or 0
            )

            sales_map[
                local_date
            ]["orders"] += 1

        cart = (
            order.cart_items
            or []
        )

        for item in cart:

            name = str(
                item.get(
                    "name",
                    "Unknown Item",
                )
            )

            try:

                quantity = int(
                    item.get(
                        "qty",
                        0,
                    )
                )

            except (
                TypeError,
                ValueError,
            ):

                quantity = 0

            try:

                price = int(
                    item.get(
                        "price",
                        0,
                    )
                )

            except (
                TypeError,
                ValueError,
            ):

                price = 0

            item_totals[
                name
            ]["quantity"] += quantity

            item_totals[
                name
            ]["revenue"] += (
                price
                * quantity
            )

    sales = []

    for sales_date, values in (
        sales_map.items()
    ):

        sales.append(
            {
                "date":
                    sales_date,

                "label":
                    sales_date.strftime(
                        "%d %b"
                    ),

                "revenue":
                    values[
                        "revenue"
                    ],

                "orders":
                    values[
                        "orders"
                    ],
            }
        )

    top_items = []

    sorted_items = sorted(
        item_totals.items(),
        key=lambda item: (
            item[1][
                "quantity"
            ]
        ),
        reverse=True,
    )

    for name, values in (
        sorted_items[:10]
    ):

        top_items.append(
            {
                "name":
                    name,

                "quantity":
                    values[
                        "quantity"
                    ],

                "revenue":
                    values[
                        "revenue"
                    ],
            }
        )

    return {
        "period_start":
            start_date,

        "period_end":
            end_date,

        "total_revenue":
            total_revenue,

        "total_orders":
            total_orders,

        "active_orders":
            int(
                active_orders
                or 0
            ),

        "completed_orders":
            completed_orders,

        "cancelled_orders":
            cancelled_orders,

        "rejected_orders":
            rejected_orders,

        "average_order_value":
            average_order_value,

        "average_preparation_minutes":
            average_preparation_minutes,

        "sales":
            sales,

        "top_items":
            top_items,
    }