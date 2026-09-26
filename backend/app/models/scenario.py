from datetime import date

from sqlalchemy import ARRAY, Boolean, Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Scenario(TimestampMixin, Base):
    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    factor: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    routes: Mapped[list[int] | None] = mapped_column(ARRAY(Integer), nullable=True)
    date_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    date_to: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    days: Mapped[str] = mapped_column(String(16), default="all", nullable=False)
    hour_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hour_to: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    comment: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
