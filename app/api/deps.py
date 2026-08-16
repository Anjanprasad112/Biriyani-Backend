from fastapi import (
    Depends,
    HTTPException,
    status,
)

from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import StaffUser


# ============================================================
# BEARER TOKEN AUTH
# ============================================================

bearer_scheme = HTTPBearer()


# ============================================================
# CURRENT USER
# ============================================================

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(
        bearer_scheme
    ),
    db: Session = Depends(get_db),
) -> StaffUser:

    token = credentials.credentials

    payload = decode_access_token(
        token
    )

    if not payload:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


    user_id = payload.get(
        "sub"
    )

    if not user_id:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


    try:

        user_id = int(
            user_id
        )

    except (
        TypeError,
        ValueError,
    ):

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


    user = db.get(
        StaffUser,
        user_id,
    )


    if (
        not user
        or not user.is_active
    ):

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )


    return user


# ============================================================
# ROLE AUTHORIZATION
# ============================================================

def require_roles(
    *allowed_roles,
):

    allowed = {
        role.value
        if hasattr(
            role,
            "value",
        )
        else str(role)
        for role in allowed_roles
    }


    def dependency(
        current_user: StaffUser = Depends(
            get_current_user
        ),
    ) -> StaffUser:

        current_role = (
            current_user.role.value
            if hasattr(
                current_user.role,
                "value",
            )
            else str(
                current_user.role
            )
        )


        if current_role not in allowed:

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )


        return current_user


    return dependency