from sqlalchemy import (
    JSON,
    Integer,
    String,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.db.base import Base


class CustomerSession(Base):

    __tablename__ = "sessions"


    phone_number: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
    )


    step: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )


    order_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )


    table_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )


    temp_item_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )


    cart: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
    )