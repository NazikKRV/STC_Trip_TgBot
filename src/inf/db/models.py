from sqlalchemy import BigInteger, ForeignKey, String, Text, Boolean, Integer
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
