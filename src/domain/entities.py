from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class BookingStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"


@dataclass
class TourEntity:
    id: int | None
    title: str
    dates: str
    price: int
    program_url: str
    included_details: str
    payment_deadline: str
    chat_link: str
    max_seats: int = 59
    is_active: bool = True


@dataclass
class BookingEntity:
    id: int | None
    user_telegram_id: int
    tour_id: int
    full_name: str
    phone: str
    age: int
    tickets_count: int
    other_participants: str
    amount: int
    status: BookingStatus = BookingStatus.PENDING
    transaction_id: str | None = None
    created_at: datetime | None = None


@dataclass
class PaymentWebhookResult:
    is_valid: bool
    booking_id: int | None = None
    status: str | None = None
    transaction_id: str | None = None
