from enum import Enum


class UserRole(
    str,
    Enum,
):

    OWNER = "OWNER"

    MANAGER = "MANAGER"

    KITCHEN = "KITCHEN"

    CASHIER = "CASHIER"


class OrderStatus(
    str,
    Enum,
):

    PENDING = "Pending"

    PAID = "Paid"

    PREPARATION = "Preparation"

    READY = "Ready"

    COLLECTED = "Collected"

    CANCELLED = "Cancelled"

    REJECTED = "Rejected"


class OrderType(
    str,
    Enum,
):

    TAKEAWAY = "Takeaway"

    DINE_IN = "Dine-in"


ACTIVE_ORDER_STATUSES = (
    OrderStatus.PAID.value,
    OrderStatus.PREPARATION.value,
    OrderStatus.READY.value,
)


COMPLETED_ORDER_STATUSES = (
    OrderStatus.COLLECTED.value,
    OrderStatus.CANCELLED.value,
    OrderStatus.REJECTED.value,
)