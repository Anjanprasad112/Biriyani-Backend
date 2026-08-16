from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class MenuItemCreate(BaseModel):

    name: str = Field(
        min_length=1,
        max_length=200,
    )

    price: int = Field(
        ge=0
    )

    inventory: int = Field(
        ge=0
    )

    is_active: bool = True


class MenuItemUpdate(BaseModel):

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )

    price: int | None = Field(
        default=None,
        ge=0,
    )

    inventory: int | None = Field(
        default=None,
        ge=0,
    )

    is_active: bool | None = None


class MenuItemRead(BaseModel):

    id: int

    name: str

    price: int

    inventory: int

    is_active: bool

    created_at: datetime

    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )