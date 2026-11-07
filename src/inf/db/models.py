from datetime import datetime
from sqlalchemy import (
    BigInteger,
    ForeignKey,
    String,
    Text,
    Boolean,
    Integer,
    DateTime,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TourModel(Base):
    __tablename__ = "tours"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255))
    dates: Mapped[str] = mapped_column(String(100))
    price: Mapped[int] = mapped_column(Integer)
    program_url: Mapped[str] = mapped_column(String(500))
    included_details: Mapped[str] = mapped_column(Text)
    payment_deadline: Mapped[str] = mapped_column(String(100))
    chat_link: Mapped[str] = mapped_column(String(500))
    max_seats: Mapped[int] = mapped_column(Integer, default=59)
    duration_days: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BookingModel(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    tour_id: Mapped[int] = mapped_column(ForeignKey("tours.id"))
    full_name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(50))
    age: Mapped[int] = mapped_column(Integer)
    tickets_count: Mapped[int] = mapped_column(Integer, default=1)
    other_participants: Mapped[str] = mapped_column(Text)
    amount: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    transaction_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="немає")
    discount_info: Mapped[str] = mapped_column(Text, default="немає")
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class UserModel(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_loyal: Mapped[bool] = mapped_column(Boolean, default=False)
    loyal_request_pending: Mapped[bool] = mapped_column(Boolean, default=False)


class PromoCodeModel(Base):
    __tablename__ = "promo_codes"

    code: Mapped[str] = mapped_column(String(100), primary_key=True)
    discount_per_person: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class FaqModel(Base):
    __tablename__ = "faqs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    button_title: Mapped[str] = mapped_column(String(255))
    answer_html: Mapped[str] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class FsmStateModel(Base):
    __tablename__ = "fsm_states"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    state: Mapped[str | None] = mapped_column(String(255), nullable=True)
    data: Mapped[str] = mapped_column(Text, default="{}")
