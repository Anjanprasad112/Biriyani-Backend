from pydantic import (
    BaseModel,
    Field,
)

from app.schemas.user import UserRead


class LoginRequest(BaseModel):

    email: str

    password: str = Field(
        min_length=6,
        max_length=200,
    )


class TokenResponse(BaseModel):

    access_token: str

    token_type: str = "bearer"

    user: UserRead