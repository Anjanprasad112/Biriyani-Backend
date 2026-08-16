from sqlalchemy import (
    String,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.db.base import Base


class Customer(Base):

    __tablename__ = "users"


    phone_number: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
    )