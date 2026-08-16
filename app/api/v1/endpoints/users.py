from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from sqlalchemy import (
    func,
    select,
)

from sqlalchemy.orm import (
    Session,
)

from app.api.deps import (
    require_roles,
)

from app.core.security import (
    hash_password,
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

from app.schemas.user import (
    UserCreate,
    UserRead,
    UserUpdate,
)


router = APIRouter(
    prefix="/users",
    tags=["users"],
)


# ============================================================
# HELPERS
# ============================================================

def role_value(
    role,
) -> str:

    if hasattr(
        role,
        "value",
    ):
        return role.value

    return str(role)


def normalize_email(
    email: str,
) -> str:

    return (
        email
        .strip()
        .lower()
    )


def ensure_email_available(
    db: Session,
    email: str,
    exclude_user_id: int | None = None,
):

    stmt = select(
        StaffUser
    ).where(
        func.lower(
            StaffUser.email
        )
        == email.lower()
    )


    if (
        exclude_user_id
        is not None
    ):

        stmt = stmt.where(
            StaffUser.id
            != exclude_user_id
        )


    existing = db.scalar(
        stmt
    )


    if existing:

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A staff account with "
                "this email already exists"
            ),
        )


def active_owner_count(
    db: Session,
    shop_id: int,
    exclude_user_id: int | None = None,
) -> int:

    stmt = select(
        func.count(
            StaffUser.id
        )
    ).where(
        StaffUser.shop_id
        == shop_id,
        StaffUser.role
        == UserRole.OWNER.value,
        StaffUser.is_active
        .is_(True),
    )


    if (
        exclude_user_id
        is not None
    ):

        stmt = stmt.where(
            StaffUser.id
            != exclude_user_id
        )


    return int(
        db.scalar(stmt)
        or 0
    )


# ============================================================
# LIST STAFF
#
# OWNER:
# full staff management
#
# MANAGER:
# read-only visibility
# ============================================================

@router.get(
    "",
    response_model=list[
        UserRead
    ],
)
def list_users(
    db: Session = Depends(
        get_db
    ),

    current_user: StaffUser = Depends(
        require_roles(
            UserRole.OWNER,
            UserRole.MANAGER,
        )
    ),
):

    stmt = (
        select(
            StaffUser
        )
        .where(
            StaffUser.shop_id
            == current_user.shop_id
        )
        .order_by(
            StaffUser.is_active.desc(),
            StaffUser.name.asc(),
        )
    )


    return list(
        db.scalars(
            stmt
        ).all()
    )


# ============================================================
# CREATE STAFF
#
# Only OWNER can create:
#
# OWNER
# KITCHEN
# CASHIER
# MANAGER
# ============================================================

@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    payload: UserCreate,

    db: Session = Depends(
        get_db
    ),

    current_user: StaffUser = Depends(
        require_roles(
            UserRole.OWNER,
        )
    ),
):

    email = normalize_email(
        payload.email
    )


    ensure_email_available(
        db,
        email,
    )


    user = StaffUser(

        shop_id=(
            current_user.shop_id
        ),

        name=(
            payload.name.strip()
        ),

        email=email,

        password_hash=(
            hash_password(
                payload.password
            )
        ),

        role=(
            payload.role.value
        ),

        is_active=(
            payload.is_active
        ),
    )


    db.add(
        user
    )

    db.commit()

    db.refresh(
        user
    )


    return user


# ============================================================
# UPDATE STAFF
#
# Supports:
#
# name
# email
# password
# role
# active/inactive
# ============================================================

@router.patch(
    "/{user_id}",
    response_model=UserRead,
)
def update_user(
    user_id: int,

    payload: UserUpdate,

    db: Session = Depends(
        get_db
    ),

    current_user: StaffUser = Depends(
        require_roles(
            UserRole.OWNER,
        )
    ),
):

    user = db.get(
        StaffUser,
        user_id,
    )


    if not user:

        raise HTTPException(
            status_code=404,
            detail=(
                "Staff user not found"
            ),
        )


    if (
        user.shop_id
        != current_user.shop_id
    ):

        raise HTTPException(
            status_code=403,
            detail=(
                "Cannot manage staff "
                "from another shop"
            ),
        )


    current_role = role_value(
        user.role
    )


    new_role = (
        payload.role.value
        if payload.role
        is not None
        else current_role
    )


    new_active = (
        payload.is_active
        if payload.is_active
        is not None
        else user.is_active
    )


    # --------------------------------------------------------
    # OWNER CANNOT LOCK THEMSELVES OUT
    # --------------------------------------------------------

    if (
        user.id
        == current_user.id
    ):

        if not new_active:

            raise HTTPException(
                status_code=400,
                detail=(
                    "You cannot deactivate "
                    "your own account"
                ),
            )


        if (
            new_role
            != UserRole.OWNER.value
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "You cannot remove your "
                    "own Owner access"
                ),
            )


    # --------------------------------------------------------
    # NEVER ALLOW LAST ACTIVE OWNER TO DISAPPEAR
    # --------------------------------------------------------

    removing_owner_access = (
        current_role
        == UserRole.OWNER.value
        and user.is_active
        and (
            new_role
            != UserRole.OWNER.value
            or not new_active
        )
    )


    if removing_owner_access:

        other_owners = (
            active_owner_count(
                db,
                user.shop_id,
                exclude_user_id=(
                    user.id
                ),
            )
        )


        if other_owners == 0:

            raise HTTPException(
                status_code=400,
                detail=(
                    "At least one active "
                    "Owner account must remain"
                ),
            )


    # --------------------------------------------------------
    # NAME
    # --------------------------------------------------------

    if (
        payload.name
        is not None
    ):

        user.name = (
            payload.name.strip()
        )


    # --------------------------------------------------------
    # EMAIL
    # --------------------------------------------------------

    if (
        payload.email
        is not None
    ):

        email = normalize_email(
            payload.email
        )


        ensure_email_available(
            db,
            email,
            exclude_user_id=(
                user.id
            ),
        )


        user.email = email


    # --------------------------------------------------------
    # PASSWORD
    # --------------------------------------------------------

    if (
        payload.password
        is not None
    ):

        user.password_hash = (
            hash_password(
                payload.password
            )
        )


    # --------------------------------------------------------
    # ROLE
    # --------------------------------------------------------

    if (
        payload.role
        is not None
    ):

        user.role = (
            payload.role.value
        )


    # --------------------------------------------------------
    # ACTIVE
    # --------------------------------------------------------

    if (
        payload.is_active
        is not None
    ):

        user.is_active = (
            payload.is_active
        )


    db.commit()

    db.refresh(
        user
    )


    return user