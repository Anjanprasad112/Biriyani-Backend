from datetime import (
    datetime,
    time,
)

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Time,
    func,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.db.base import Base


class ShopSettings(Base):

    __tablename__ = "shop_settings"


    shop_id: Mapped[int] = mapped_column(
        ForeignKey(
            "shops.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )


    accepting_orders: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )


    default_preparation_minutes: Mapped[
        int
    ] = mapped_column(
        Integer,
        nullable=False,
        default=20,
    )


    warning_active_orders: Mapped[
        int
    ] = mapped_column(
        Integer,
        nullable=False,
        default=30,
    )


    max_active_orders: Mapped[
        int
    ] = mapped_column(
        Integer,
        nullable=False,
        default=40,
    )


    opening_time: Mapped[
        time | None
    ] = mapped_column(
        Time,
        nullable=True,
    )


    closing_time: Mapped[
        time | None
    ] = mapped_column(
        Time,
        nullable=True,
    )


    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )