from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    require_roles,
)

from app.core.config import settings

from app.db.session import get_db

from app.models.enums import (
    UserRole,
)

from app.models.user import (
    StaffUser,
)

from app.schemas.settings import (
    CapacityRead,
    ShopSettingsRead,
    ShopSettingsUpdate,
)

from app.services.settings_service import (
    get_capacity,
    get_or_create_shop_settings,
)


router = APIRouter(
    prefix="/settings",
    tags=["settings"],
)


@router.get(
    "/shop",
    response_model=ShopSettingsRead,
)
def get_shop_settings(
    db: Session = Depends(
        get_db
    ),
    current_user: StaffUser = Depends(
        get_current_user
    ),
):

    return get_or_create_shop_settings(
        db=db,
        shop_id=current_user.shop_id,
    )


@router.patch(
    "/shop",
    response_model=ShopSettingsRead,
)
def update_shop_settings(
    payload: ShopSettingsUpdate,
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

    shop_settings = (
        get_or_create_shop_settings(
            db=db,
            shop_id=current_user.shop_id,
        )
    )

    data = payload.model_dump(
        exclude_unset=True
    )

    warning_value = data.get(
        "warning_active_orders",
        shop_settings.warning_active_orders,
    )

    max_value = data.get(
        "max_active_orders",
        shop_settings.max_active_orders,
    )

    if warning_value > max_value:

        raise HTTPException(
            status_code=400,
            detail=(
                "warning_active_orders "
                "cannot be greater than "
                "max_active_orders"
            ),
        )

    for field, value in data.items():

        setattr(
            shop_settings,
            field,
            value,
        )

    db.commit()

    db.refresh(
        shop_settings
    )

    return shop_settings


@router.get(
    "/capacity",
    response_model=CapacityRead,
)
def capacity(
    db: Session = Depends(
        get_db
    ),
    current_user: StaffUser = Depends(
        get_current_user
    ),
):

    return get_capacity(
        db=db,
        shop_id=current_user.shop_id,
    )