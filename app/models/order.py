from datetime import datetime

from sqlalchemy import (
    DateTime,
    Integer,
    JSON,
    String,
    Text,
    func,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.db.base import Base


class Order(Base):

    __tablename__ = "orders"


    order_id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
    )


    phone_number: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )


    order_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )


    table_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )


    total_amount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )


    cart_items: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
    )


    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Pending",
        index=True,
    )


    status_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )


    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )


    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


    preparation_started_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


    estimated_ready_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


    ready_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


    completed_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )