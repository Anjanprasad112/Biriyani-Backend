from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from app.models.enums import (
    UserRole,
)


class UserCreate(BaseModel):

    name: str = Field(
        min_length=2,
        max_length=120,
    )

    email: str = Field(
        min_length=5,
        max_length=255,
    )

    password: str = Field(
        min_length=8,
        max_length=128,
    )

    role: UserRole

    is_active: bool = True


class UserUpdate(BaseModel):

    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=120,
    )

    email: str | None = Field(
        default=None,
        min_length=5,
        max_length=255,
    )

    password: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
    )

    role: UserRole | None = None

    is_active: bool | None = None


class UserRead(BaseModel):

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int

    shop_id: int

    name: str

    email: str

    role: UserRole

    is_active: bool

    created_at: datetime

    updated_at: datetime | None = None