from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from sqlalchemy import select

from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
)

from app.core.security import (
    create_access_token,
    verify_password,
)

from app.db.session import get_db

from app.models.user import StaffUser

from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
)

from app.schemas.user import (
    UserRead,
)


router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    payload: LoginRequest,
    db: Session = Depends(
        get_db
    ),
):

    email = (
        payload.email
        .strip()
        .lower()
    )

    user = db.scalar(
        select(
            StaffUser
        ).where(
            StaffUser.email == email
        )
    )

    if (
        not user
        or not verify_password(
            payload.password,
            user.password_hash,
        )
    ):

        raise HTTPException(
            status_code=401,
            detail=(
                "Invalid email or password"
            ),
        )

    if not user.is_active:

        raise HTTPException(
            status_code=403,
            detail=(
                "User account is disabled"
            ),
        )

    access_token = (
        create_access_token(
            user.id
        )
    )

    return TokenResponse(
        access_token=access_token,
        user=user,
    )


@router.get(
    "/me",
    response_model=UserRead,
)
def get_me(
    current_user: StaffUser = Depends(
        get_current_user
    ),
):

    return current_user