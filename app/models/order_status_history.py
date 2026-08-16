from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.db.base import Base


class OrderStatusHistory(Base):

    __tablename__ = (
        "order_status_history"
    )


    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )


    order_id: Mapped[str] = mapped_column(
        ForeignKey(
            "orders.order_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )


    old_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )


    new_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )


    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )


    changed_by_user_id: Mapped[
        int | None
    ] = mapped_column(
        ForeignKey(
            "staff_users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )


    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )