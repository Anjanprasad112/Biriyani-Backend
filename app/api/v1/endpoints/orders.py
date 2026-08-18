from datetime import date
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)

from pydantic import BaseModel

from sqlalchemy import (
    inspect,
    text,
)

from sqlalchemy.exc import (
    SQLAlchemyError,
)

from sqlalchemy.orm import (
    Session,
)

from app.api.deps import (
    require_roles,
)

from app.db.session import (
    get_db,
)

from app.models.enums import (
    UserRole,
)

from app.models.user import (
    StaffUser,
)
from legacy.whatsapp_payment_app import (
    send_reply,
)

# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/orders",
    tags=["orders"],
)


# ============================================================
# ROLES
# ============================================================

ALL_STAFF = (
    UserRole.OWNER,
    UserRole.MANAGER,
    UserRole.KITCHEN,
    UserRole.CASHIER,
)


# ============================================================
# PROJECT B STATUS VALUES
#
# DO NOT CHANGE THESE.
# ============================================================

VALID_STATUSES = {
    "Pending",
    "Paid",
    "Preparation",
    "Ready",
    "Collected",
    "Cancelled",
    "Rejected",
}


# ============================================================
# REQUEST
# ============================================================

class OrderStatusUpdateRequest(BaseModel):
    status: str
    reason: str | None = None


# ============================================================
# TABLE METADATA CACHE
#
# This allows the endpoint to work with the actual legacy
# Project B orders table without assuming optional timestamp
# columns exist.
# ============================================================

_TABLE_INFO_CACHE: dict[
    str,
    dict[str, dict[str, Any]],
] = {}


def _table_info(
    db: Session,
    table_name: str,
) -> dict[str, dict[str, Any]]:

    cached = _TABLE_INFO_CACHE.get(
        table_name
    )

    if cached is not None:
        return cached

    inspector = inspect(
        db.get_bind()
    )

    if not inspector.has_table(
        table_name
    ):
        _TABLE_INFO_CACHE[
            table_name
        ] = {}

        return {}

    columns = (
        inspector.get_columns(
            table_name
        )
    )

    info = {
        column["name"]: column
        for column in columns
    }

    _TABLE_INFO_CACHE[
        table_name
    ] = info

    return info


def _table_columns(
    db: Session,
    table_name: str,
) -> set[str]:

    return set(
        _table_info(
            db,
            table_name,
        ).keys()
    )


# ============================================================
# ROLE HELPER
# ============================================================

def _role_value(
    role: Any,
) -> str:

    if hasattr(
        role,
        "value",
    ):
        value = role.value
    else:
        value = role

    return str(
        value
    ).upper()


# ============================================================
# STATUS HELPER
# ============================================================

def _clean_status(
    value: Any,
) -> str:

    if hasattr(
        value,
        "value",
    ):
        value = value.value

    return str(
        value
    ).strip()


def _validate_status_name(
    status_value: str,
) -> str:

    status_value = (
        status_value.strip()
    )

    if (
        status_value
        not in VALID_STATUSES
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid order status"
            ),
        )

    return status_value


# ============================================================
# GLOBAL ORDER WORKFLOW
#
# Razorpay alone handles:
#
# Pending -> Paid
#
# Staff API handles everything after payment.
# ============================================================

def _validate_transition(
    current_status: str,
    target_status: str,
) -> None:

    allowed: dict[
        str,
        set[str],
    ] = {

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

    allowed_targets = (
        allowed.get(
            current_status,
            set(),
        )
    )

    if (
        target_status
        not in allowed_targets
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot move order from "
                f"{current_status} to "
                f"{target_status}"
            ),
        )


# ============================================================
# ROLE-BASED WORKFLOW
# ============================================================

def _validate_role_transition(
    current_user: StaffUser,
    current_status: str,
    target_status: str,
) -> None:

    role = _role_value(
        current_user.role
    )

    # --------------------------------------------------------
    # OWNER / MANAGER
    # --------------------------------------------------------

    if role in {
        "OWNER",
        "MANAGER",
    }:
        return

    # --------------------------------------------------------
    # KITCHEN
    #
    # Paid -> Preparation
    # Preparation -> Ready
    #
    # Kitchen cannot collect.
    # --------------------------------------------------------

    if role == "KITCHEN":

        allowed = {
            (
                "Paid",
                "Preparation",
            ),
            (
                "Preparation",
                "Ready",
            ),
        }

        if (
            current_status,
            target_status,
        ) not in allowed:

            raise HTTPException(
                status_code=403,
                detail=(
                    "Kitchen staff can only "
                    "move New orders to Preparing "
                    "and Preparing orders to Ready"
                ),
            )

        return

    # --------------------------------------------------------
    # CASHIER
    #
    # Ready -> Collected only.
    # --------------------------------------------------------

    if role == "CASHIER":

        if (
            current_status != "Ready"
            or
            target_status
            != "Collected"
        ):
            raise HTTPException(
                status_code=403,
                detail=(
                    "Cashier can only mark "
                    "Ready orders as Collected"
                ),
            )

        return

    raise HTTPException(
        status_code=403,
        detail=(
            "You do not have permission "
            "to update orders"
        ),
    )


# ============================================================
# CANCEL / REJECT REASON
# ============================================================

def _validate_reason(
    target_status: str,
    reason: str | None,
) -> str | None:

    clean_reason = (
        reason.strip()
        if reason
        else None
    )

    if (
        target_status
        in {
            "Cancelled",
            "Rejected",
        }
        and
        not clean_reason
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "A reason is required "
                f"when marking an order "
                f"as {target_status}"
            ),
        )

    return clean_reason


# ============================================================
# GET SINGLE ORDER FROM DATABASE
# ============================================================

def _get_order_row(
    db: Session,
    order_id: str,
    for_update: bool = False,
) -> dict[str, Any] | None:

    sql = """
        SELECT *
        FROM orders
        WHERE order_id = :order_id
        LIMIT 1
    """

    if for_update:
        sql = """
            SELECT *
            FROM orders
            WHERE order_id = :order_id
            LIMIT 1
            FOR UPDATE
        """

    row = (
        db.execute(
            text(sql),
            {
                "order_id":
                    order_id,
            },
        )
        .mappings()
        .first()
    )

    if row is None:
        return None

    return dict(row)


# ============================================================
# HISTORY HELPERS
#
# History is optional here.
#
# If the order_status_history table matches the legacy order
# identifier, history is recorded.
#
# If an older incompatible history table exists, the actual
# order update still succeeds.
# ============================================================

def _history_order_key(
    db: Session,
    order: dict[str, Any],
) -> Any:

    history_info = (
        _table_info(
            db,
            "order_status_history",
        )
    )

    order_id_info = (
        history_info.get(
            "order_id"
        )
    )

    if not order_id_info:
        return order.get(
            "order_id"
        )

    column_type = (
        order_id_info.get(
            "type"
        )
    )

    try:
        python_type = (
            column_type.python_type
        )
    except Exception:
        python_type = str

    # Some old versions of the history table used
    # the numeric internal orders.id.
    if (
        python_type is int
        and
        order.get("id")
        is not None
    ):
        return order["id"]

    return order.get(
        "order_id"
    )


def _record_history(
    db: Session,
    order: dict[str, Any],
    from_status: str,
    to_status: str,
    current_user: StaffUser,
    reason: str | None,
) -> None:

    history_columns = (
        _table_columns(
            db,
            "order_status_history",
        )
    )

    if not history_columns:
        return

    required = {
        "order_id",
        "from_status",
        "to_status",
    }

    if not required.issubset(
        history_columns
    ):
        return

    values: dict[str, Any] = {
        "order_id":
            _history_order_key(
                db,
                order,
            ),

        "from_status":
            from_status,

        "to_status":
            to_status,
    }

    insert_columns = [
        "order_id",
        "from_status",
        "to_status",
    ]

    if (
        "changed_by_user_id"
        in history_columns
    ):
        insert_columns.append(
            "changed_by_user_id"
        )

        values[
            "changed_by_user_id"
        ] = current_user.id

    if (
        "reason"
        in history_columns
    ):
        insert_columns.append(
            "reason"
        )

        values["reason"] = (
            reason
        )

    column_sql = ", ".join(
        insert_columns
    )

    value_sql = ", ".join(
        f":{name}"
        for name in insert_columns
    )

    sql = (
        f"""
        INSERT INTO order_status_history
        ({column_sql})
        VALUES ({value_sql})
        """
    )

    # Do not allow an incompatible old history
    # table to break the actual order workflow.
    try:

        with db.begin_nested():

            db.execute(
                text(sql),
                values,
            )

    except SQLAlchemyError:
        pass


# ============================================================
# LOAD STATUS HISTORY FOR ONE ORDER
# ============================================================

def _load_history(
    db: Session,
    order: dict[str, Any],
) -> list[dict[str, Any]]:

    history_columns = (
        _table_columns(
            db,
            "order_status_history",
        )
    )

    if (
        "order_id"
        not in history_columns
    ):
        return []

    order_key = (
        _history_order_key(
            db,
            order,
        )
    )

    if order_key is None:
        return []

    if (
        "changed_at"
        in history_columns
    ):
        order_by = (
            "changed_at ASC"
        )

    elif (
        "created_at"
        in history_columns
    ):
        order_by = (
            "created_at ASC"
        )

    elif (
        "id"
        in history_columns
    ):
        order_by = "id ASC"

    else:
        order_by = "order_id"

    try:

        rows = (
            db.execute(
                text(
                    f"""
                    SELECT *
                    FROM order_status_history
                    WHERE order_id = :order_id
                    ORDER BY {order_by}
                    """
                ),
                {
                    "order_id":
                        order_key,
                },
            )
            .mappings()
            .all()
        )

        return [
            dict(row)
            for row in rows
        ]

    except SQLAlchemyError:
        return []


# ============================================================
# GET /api/v1/orders
#
# Supported:
#
# ?status=Paid
# ?status=Preparation
# ?status=Ready
# ?status=Collected
#
# ?search=ORD-123
# ?search=919999999999
#
# ?date_from=2026-08-01
# ?date_to=2026-08-15
#
# ?offset=0
# ?limit=25
# ============================================================

@router.get("")
def list_orders(

    order_status: str | None = Query(
        default=None,
        alias="status",
    ),

    date_from: date | None = Query(
        default=None,
    ),

    date_to: date | None = Query(
        default=None,
    ),

    search: str | None = Query(
        default=None,
        max_length=120,
    ),

    offset: int = Query(
        default=0,
        ge=0,
    ),

    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),

    db: Session = Depends(
        get_db
    ),

    current_user: StaffUser = Depends(
        require_roles(
            *ALL_STAFF
        )
    ),

) -> list[dict[str, Any]]:

    # Keeps authentication / role checking active.
    _ = current_user

    conditions: list[str] = []

    parameters: dict[
        str,
        Any,
    ] = {
        "offset": offset,
        "limit": limit,
    }

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    if order_status:

        clean_status = (
            _validate_status_name(
                order_status
            )
        )

        conditions.append(
            "status = :status"
        )

        parameters[
            "status"
        ] = clean_status

    # --------------------------------------------------------
    # FROM DATE
    # --------------------------------------------------------

    if date_from:

        conditions.append(
            "DATE(created_at) >= :date_from"
        )

        parameters[
            "date_from"
        ] = date_from

    # --------------------------------------------------------
    # TO DATE
    # --------------------------------------------------------

    if date_to:

        conditions.append(
            "DATE(created_at) <= :date_to"
        )

        parameters[
            "date_to"
        ] = date_to

    # --------------------------------------------------------
    # SEARCH
    # --------------------------------------------------------

    clean_search = (
        search.strip()
        if search
        else ""
    )

    if clean_search:

        conditions.append(
            """
            (
                CAST(order_id AS TEXT)
                    ILIKE :search

                OR

                CAST(phone_number AS TEXT)
                    ILIKE :search

                OR

                COALESCE(
                    CAST(order_type AS TEXT),
                    ''
                )
                    ILIKE :search

                OR

                COALESCE(
                    CAST(table_number AS TEXT),
                    ''
                )
                    ILIKE :search
            )
            """
        )

        parameters[
            "search"
        ] = (
            f"%{clean_search}%"
        )

    # --------------------------------------------------------
    # WHERE
    # --------------------------------------------------------

    where_sql = ""

    if conditions:

        where_sql = (
            "WHERE "
            + " AND ".join(
                conditions
            )
        )

    # --------------------------------------------------------
    # QUERY
    # --------------------------------------------------------

    sql = f"""
        SELECT *
        FROM orders

        {where_sql}

        ORDER BY created_at DESC

        OFFSET :offset
        LIMIT :limit
    """

    rows = (
        db.execute(
            text(sql),
            parameters,
        )
        .mappings()
        .all()
    )

    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# GET /api/v1/orders/{order_id}
# ============================================================

@router.get(
    "/{order_id}"
)
def get_order(

    order_id: str,

    db: Session = Depends(
        get_db
    ),

    current_user: StaffUser = Depends(
        require_roles(
            *ALL_STAFF
        )
    ),

) -> dict[str, Any]:

    _ = current_user

    order = (
        _get_order_row(
            db,
            order_id,
        )
    )

    if order is None:

        raise HTTPException(
            status_code=404,
            detail=(
                "Order not found"
            ),
        )

    # Useful for the expandable Order History UI.
    order[
        "status_history"
    ] = _load_history(
        db,
        order,
    )

    return order


# ============================================================
# PATCH /api/v1/orders/{order_id}/status
#
# OWNER / MANAGER
#
# Paid
#   -> Preparation
#   -> Cancelled
#   -> Rejected
#
# Preparation
#   -> Ready
#   -> Cancelled
#
# Ready
#   -> Collected
#
# KITCHEN
#
# Paid -> Preparation
# Preparation -> Ready
#
# CASHIER
#
# Ready -> Collected
#
#
# IMPORTANT
#
# Pending -> Paid is NOT handled here.
#
# The existing Razorpay webhook owns payment confirmation.
# ============================================================

@router.patch(
    "/{order_id}/status"
)
def update_order_status(

    order_id: str,

    payload:
        OrderStatusUpdateRequest,

    db: Session = Depends(
        get_db
    ),

    current_user: StaffUser = Depends(
        require_roles(
            *ALL_STAFF
        )
    ),

) -> dict[str, Any]:

    target_status = (
        _validate_status_name(
            payload.status
        )
    )

    try:

        # ----------------------------------------------------
        # LOCK ORDER
        #
        # Prevents two staff members from moving the same
        # order at exactly the same time.
        # ----------------------------------------------------

        order = (
            _get_order_row(
                db,
                order_id,
                for_update=True,
            )
        )

        if order is None:

            raise HTTPException(
                status_code=404,
                detail=(
                    "Order not found"
                ),
            )

        current_status = (
            _clean_status(
                order.get(
                    "status",
                    "",
                )
            )
        )

        # ----------------------------------------------------
        # GLOBAL WORKFLOW
        # ----------------------------------------------------

        _validate_transition(
            current_status,
            target_status,
        )

        # ----------------------------------------------------
        # ROLE WORKFLOW
        # ----------------------------------------------------

        _validate_role_transition(
            current_user,
            current_status,
            target_status,
        )

        # ----------------------------------------------------
        # REASON
        # ----------------------------------------------------

        clean_reason = (
            _validate_reason(
                target_status,
                payload.reason,
            )
        )

        # ----------------------------------------------------
        # CHECK ACTUAL PROJECT B COLUMNS
        # ----------------------------------------------------

        order_columns = (
            _table_columns(
                db,
                "orders",
            )
        )

        assignments: list[str] = [
            "status = :new_status"
        ]

        parameters: dict[
            str,
            Any,
        ] = {
            "new_status":
                target_status,

            "order_id":
                order_id,
        }

        # ----------------------------------------------------
        # UPDATED AT
        # ----------------------------------------------------

        if (
            "updated_at"
            in order_columns
        ):
            assignments.append(
                "updated_at = NOW()"
            )

        # ----------------------------------------------------
        # PAID
        #
        # Staff never moves Pending -> Paid.
        # Razorpay handles that.
        # ----------------------------------------------------

        # ----------------------------------------------------
        # PREPARATION
        # ----------------------------------------------------

        if (
            target_status
            == "Preparation"
        ):

            if (
                "preparation_started_at"
                in order_columns
            ):
                assignments.append(
                    "preparation_started_at = NOW()"
                )

            if (
                "status_reason"
                in order_columns
            ):
                assignments.append(
                    "status_reason = NULL"
                )

        # ----------------------------------------------------
        # READY
        # ----------------------------------------------------

        elif (
            target_status
            == "Ready"
        ):

            if (
                "ready_at"
                in order_columns
            ):
                assignments.append(
                    "ready_at = NOW()"
                )

            if (
                "status_reason"
                in order_columns
            ):
                assignments.append(
                    "status_reason = NULL"
                )

        # ----------------------------------------------------
        # COLLECTED
        # ----------------------------------------------------

        elif (
            target_status
            == "Collected"
        ):

            # Legacy Project B uses completed_at.
            if (
                "completed_at"
                in order_columns
            ):
                assignments.append(
                    "completed_at = NOW()"
                )

            # If your newer model also contains collected_at,
            # set it as well.
            if (
                "collected_at"
                in order_columns
            ):
                assignments.append(
                    "collected_at = NOW()"
                )

            if (
                "status_reason"
                in order_columns
            ):
                assignments.append(
                    "status_reason = NULL"
                )

        # ----------------------------------------------------
        # CANCELLED
        # ----------------------------------------------------

        elif (
            target_status
            == "Cancelled"
        ):

            if (
                "cancelled_at"
                in order_columns
            ):
                assignments.append(
                    "cancelled_at = NOW()"
                )

            if (
                "status_reason"
                in order_columns
            ):
                assignments.append(
                    "status_reason = :reason"
                )

                parameters[
                    "reason"
                ] = clean_reason

        # ----------------------------------------------------
        # REJECTED
        # ----------------------------------------------------

        elif (
            target_status
            == "Rejected"
        ):

            if (
                "rejected_at"
                in order_columns
            ):
                assignments.append(
                    "rejected_at = NOW()"
                )

            if (
                "status_reason"
                in order_columns
            ):
                assignments.append(
                    "status_reason = :reason"
                )

                parameters[
                    "reason"
                ] = clean_reason

        # ----------------------------------------------------
        # UPDATE SQL
        # ----------------------------------------------------

        assignment_sql = (
            ", ".join(
                assignments
            )
        )

        update_sql = f"""
            UPDATE orders

            SET {assignment_sql}

            WHERE order_id = :order_id

            RETURNING *
        """

        updated_row = (
            db.execute(
                text(
                    update_sql
                ),
                parameters,
            )
            .mappings()
            .first()
        )

        if updated_row is None:

            db.rollback()

            raise HTTPException(
                status_code=404,
                detail=(
                    "Order not found"
                ),
            )

        updated_order = dict(
            updated_row
        )

        # ----------------------------------------------------
        # HISTORY
        # ----------------------------------------------------

        _record_history(

            db=db,

            order=order,

            from_status=(
                current_status
            ),

            to_status=(
                target_status
            ),

            current_user=(
                current_user
            ),

            reason=(
                clean_reason
            ),
        )

        # ----------------------------------------------------
        # COMMIT
        # ----------------------------------------------------

        db.commit()

        # ----------------------------------------------------
        # WHATSAPP - ORDER READY
        # ----------------------------------------------------

        if (
            current_status == "Preparation"
            and target_status == "Ready"
        ):
            customer_phone = (
                updated_order.get(
                    "phone_number"
                )
            )

            if customer_phone:
                try:
                    send_reply(
                        str(customer_phone),
                        (
                            "✅ *Order Ready!*\n\n"
                            f"Your order ({order_id}) "
                            "has been prepared and is "
                            "ready to be collected.\n\n"
                            "Thank you for choosing "
                            "Watave's Biriyani Point!"
                        ),
                    )

                except Exception as exc:
                    print(
                        "Could not send Ready "
                        "WhatsApp notification:",
                        exc,
                    )

        # ----------------------------------------------------
        # RETURN FRESH ORDER
        # ----------------------------------------------------

        fresh_order = (
            _get_order_row(
                db,
                order_id,
            )
        )

        if fresh_order is None:

            return updated_order

        fresh_order[
            "status_history"
        ] = _load_history(
            db,
            fresh_order,
        )

        return fresh_order

    except HTTPException:

        db.rollback()

        raise

    except Exception as exc:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not update order: "
                f"{str(exc)}"
            ),
        ) from exc