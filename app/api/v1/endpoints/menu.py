from typing import Any, Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from pydantic import (
    BaseModel,
    Field,
)

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import StaffUser


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/menu",
    tags=["menu"],
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


MANAGEMENT = (
    UserRole.OWNER,
    UserRole.MANAGER,
)


# ============================================================
# MENU CATEGORY
# ============================================================

MenuCategory = Literal[
    "BIRYANI",
    "CHICKEN_65_WEIGHT",
    "CHICKEN_65_PACKS",
]


# ============================================================
# REQUEST MODELS
#
# track_inventory = False
#     Inventory quantity is ignored.
#
# track_inventory = True
#     Inventory quantity is enforced.
#
# inventory = 0 with track_inventory = True
#     Item is sold out.
# ============================================================

class MenuCreateRequest(BaseModel):

    name: str = Field(
        min_length=1,
        max_length=120,
    )

    price: int = Field(
        ge=0,
    )

    inventory: int = Field(
        default=0,
        ge=0,
    )

    track_inventory: bool = False

    is_active: bool = True

    category: MenuCategory


class MenuUpdateRequest(BaseModel):

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
    )

    price: int | None = Field(
        default=None,
        ge=0,
    )

    inventory: int | None = Field(
        default=None,
        ge=0,
    )

    track_inventory: bool | None = None

    is_active: bool | None = None

    category: MenuCategory | None = None


# ============================================================
# HELPERS
# ============================================================

def _role_value(
    role: Any,
) -> str:

    if hasattr(
        role,
        "value",
    ):
        return str(
            role.value
        ).upper()

    return str(
        role
    ).upper()


def _get_menu_item(
    db: Session,
    item_id: int,
) -> dict[str, Any] | None:

    row = (
        db.execute(
            text(
                """
                SELECT *
                FROM menu
                WHERE id = :item_id
                LIMIT 1
                """
            ),
            {
                "item_id": item_id,
            },
        )
        .mappings()
        .first()
    )

    if row is None:
        return None

    return dict(
        row
    )


# ============================================================
# GET /api/v1/menu
#
# OWNER
# MANAGER
# KITCHEN
# CASHIER
# ============================================================

@router.get("")
def get_menu(

    db: Session = Depends(
        get_db
    ),

    current_user: StaffUser = Depends(
        require_roles(
            *ALL_STAFF
        )
    ),

) -> list[dict[str, Any]]:

    _ = current_user

    rows = (
        db.execute(
            text(
                """
                SELECT *
                FROM menu

                ORDER BY
                    is_active DESC,
                    name ASC
                """
            )
        )
        .mappings()
        .all()
    )

    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# POST /api/v1/menu
#
# OWNER / MANAGER ONLY
# ============================================================

@router.post("")
def create_menu_item(

    payload: MenuCreateRequest,

    db: Session = Depends(
        get_db
    ),

    current_user: StaffUser = Depends(
        require_roles(
            *MANAGEMENT
        )
    ),

) -> dict[str, Any]:

    _ = current_user


    # --------------------------------------------------------
    # NAME
    # --------------------------------------------------------

    name = (
        payload.name
        .strip()
    )


    if not name:

        raise HTTPException(
            status_code=400,
            detail="Item name is required",
        )


    # --------------------------------------------------------
    # DUPLICATE NAME
    # --------------------------------------------------------

    duplicate = (
        db.execute(
            text(
                """
                SELECT id
                FROM menu

                WHERE
                    LOWER(name)
                    = LOWER(:name)

                LIMIT 1
                """
            ),
            {
                "name": name,
            },
        )
        .mappings()
        .first()
    )


    if duplicate:

        raise HTTPException(
            status_code=409,
            detail=(
                "A menu item with this "
                "name already exists"
            ),
        )


    # --------------------------------------------------------
    # CREATE
    # --------------------------------------------------------

    try:

        row = (
            db.execute(
                text(
                    """
                    INSERT INTO menu (
                        name,
                        price,
                        inventory,
                        track_inventory,
                        is_active,
                        category
                    )

                    VALUES (
                        :name,
                        :price,
                        :inventory,
                        :track_inventory,
                        :is_active,
                        :category
                    )

                    RETURNING *
                    """
                ),
                {
                    "name":
                        name,

                    "price":
                        payload.price,

                    "inventory":
                        payload.inventory,

                    "track_inventory":
                        payload.track_inventory,

                    "is_active":
                        payload.is_active,

                    "category":
                        payload.category,
                },
            )
            .mappings()
            .first()
        )


        if row is None:

            db.rollback()

            raise HTTPException(
                status_code=500,
                detail=(
                    "Could not create "
                    "menu item"
                ),
            )


        db.commit()


        return dict(
            row
        )


    except HTTPException:

        db.rollback()

        raise


    except Exception as exc:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not create menu item: "
                f"{str(exc)}"
            ),
        ) from exc


# ============================================================
# PATCH /api/v1/menu/{item_id}
#
# OWNER / MANAGER:
#   name
#   price
#   inventory
#   track_inventory
#   is_active
#   category
#
# KITCHEN / CASHIER:
#   is_active ONLY
# ============================================================

@router.patch(
    "/{item_id}"
)
def update_menu_item(

    item_id: int,

    payload: MenuUpdateRequest,

    db: Session = Depends(
        get_db
    ),

    current_user: StaffUser = Depends(
        require_roles(
            *ALL_STAFF
        )
    ),

) -> dict[str, Any]:

    # --------------------------------------------------------
    # LOAD ITEM
    # --------------------------------------------------------

    existing = (
        _get_menu_item(
            db,
            item_id,
        )
    )


    if existing is None:

        raise HTTPException(
            status_code=404,
            detail="Menu item not found",
        )


    role = _role_value(
        current_user.role
    )


    payload_data = (
        payload.model_dump(
            exclude_unset=True
        )
    )


    if not payload_data:

        raise HTTPException(
            status_code=400,
            detail="No fields to update",
        )


    # ========================================================
    # KITCHEN / CASHIER
    #
    # Availability only.
    # ========================================================

    if role in {
        "KITCHEN",
        "CASHIER",
    }:

        supplied_fields = set(
            payload_data.keys()
        )


        if supplied_fields != {
            "is_active"
        }:

            raise HTTPException(
                status_code=403,
                detail=(
                    "Kitchen and Cashier "
                    "can only change menu "
                    "availability"
                ),
            )


    # ========================================================
    # OWNER / MANAGER
    # ========================================================

    elif role not in {
        "OWNER",
        "MANAGER",
    }:

        raise HTTPException(
            status_code=403,
            detail=(
                "You do not have permission "
                "to update menu items"
            ),
        )


    # --------------------------------------------------------
    # NAME
    # --------------------------------------------------------

    if "name" in payload_data:

        name = (
            str(
                payload_data[
                    "name"
                ]
            )
            .strip()
        )


        if not name:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Item name is required"
                ),
            )


        duplicate = (
            db.execute(
                text(
                    """
                    SELECT id
                    FROM menu

                    WHERE
                        LOWER(name)
                            = LOWER(:name)

                        AND id
                            != :item_id

                    LIMIT 1
                    """
                ),
                {
                    "name":
                        name,

                    "item_id":
                        item_id,
                },
            )
            .mappings()
            .first()
        )


        if duplicate:

            raise HTTPException(
                status_code=409,
                detail=(
                    "A menu item with this "
                    "name already exists"
                ),
            )


        payload_data[
            "name"
        ] = name


    # ========================================================
    # SAFE UPDATE FIELDS
    # ========================================================

    allowed_columns = {
        "name",
        "price",
        "inventory",
        "track_inventory",
        "is_active",
        "category",
    }


    update_fields = {

        key:
            value

        for (
            key,
            value,
        )
        in payload_data.items()

        if key
        in allowed_columns

    }


    if not update_fields:

        raise HTTPException(
            status_code=400,
            detail=(
                "No valid fields "
                "to update"
            ),
        )


    # ========================================================
    # BUILD SQL
    # ========================================================

    assignments: list[str] = []


    parameters: dict[
        str,
        Any,
    ] = {
        "item_id":
            item_id,
    }


    for (
        column,
        value,
    ) in update_fields.items():

        assignments.append(
            f"{column} = :{column}"
        )

        parameters[
            column
        ] = value


    assignments.append(
        "updated_at = NOW()"
    )


    assignment_sql = (
        ", ".join(
            assignments
        )
    )


    # ========================================================
    # UPDATE
    # ========================================================

    try:

        row = (
            db.execute(
                text(
                    f"""
                    UPDATE menu

                    SET
                        {assignment_sql}

                    WHERE
                        id = :item_id

                    RETURNING *
                    """
                ),
                parameters,
            )
            .mappings()
            .first()
        )


        if row is None:

            db.rollback()

            raise HTTPException(
                status_code=404,
                detail=(
                    "Menu item not found"
                ),
            )


        db.commit()


        return dict(
            row
        )


    except HTTPException:

        db.rollback()

        raise


    except Exception as exc:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not update menu item: "
                f"{str(exc)}"
            ),
        ) from exc


# ============================================================
# DELETE /api/v1/menu/{item_id}
#
# OWNER / MANAGER ONLY
#
# SOFT DELETE:
# is_active = FALSE
#
# Historical order/cart references stay intact.
# ============================================================

@router.delete(
    "/{item_id}"
)
def delete_menu_item(

    item_id: int,

    db: Session = Depends(
        get_db
    ),

    current_user: StaffUser = Depends(
        require_roles(
            *MANAGEMENT
        )
    ),

) -> dict[str, Any]:

    _ = current_user


    existing = (
        _get_menu_item(
            db,
            item_id,
        )
    )


    if existing is None:

        raise HTTPException(
            status_code=404,
            detail="Menu item not found",
        )


    try:

        db.execute(
            text(
                """
                UPDATE menu

                SET
                    is_active = FALSE,
                    updated_at = NOW()

                WHERE
                    id = :item_id
                """
            ),
            {
                "item_id":
                    item_id,
            },
        )


        db.commit()


        return {
            "status":
                "deleted",

            "id":
                item_id,
        }


    except Exception as exc:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not remove menu item: "
                f"{str(exc)}"
            ),
        ) from exc