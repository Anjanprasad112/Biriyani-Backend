from datetime import (
    datetime,
    timedelta,
    timezone,
)

from jose import (
    JWTError,
    jwt,
)

from pwdlib import PasswordHash

from app.core.config import settings


# ============================================================
# PASSWORD HASHING
#
# Uses Argon2 through pwdlib.
# ============================================================

password_hasher = (
    PasswordHash.recommended()
)


def hash_password(
    password: str,
) -> str:

    if not password:
        raise ValueError(
            "Password cannot be empty"
        )

    return password_hasher.hash(
        password
    )


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:

    if (
        not plain_password
        or not hashed_password
    ):
        return False

    try:

        return password_hasher.verify(
            plain_password,
            hashed_password,
        )

    except Exception:

        return False


# ============================================================
# JWT ACCESS TOKENS
# ============================================================

def create_access_token(
    subject: str | int,
    expires_minutes: int | None = None,
) -> str:

    if expires_minutes is None:

        expires_minutes = (
            settings
            .access_token_expire_minutes
        )

    expires_at = (
        datetime.now(
            timezone.utc
        )
        + timedelta(
            minutes=expires_minutes
        )
    )

    payload = {
        "sub": str(subject),
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=(
            settings.jwt_algorithm
        ),
    )


def decode_access_token(
    token: str,
) -> dict | None:

    try:

        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[
                settings.jwt_algorithm
            ],
        )

    except JWTError:

        return None