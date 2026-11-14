from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class BookingStatus(str, Enum):
    PENDING = "pending"
    WAITING_MANAGER = "waiting_manager"
    WAITING_RECEIPT = "waiting_receipt"
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
    duration_days: int = 1
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
    notes: str = "немає"
    discount_info: str = "немає"
    username: str | None = None
    created_at: datetime | None = None


@dataclass
class UserEntity:
    telegram_id: int
    full_name: str | None = None
    phone: str | None = None
    username: str | None = None
    is_loyal: bool = False
    loyal_request_pending: bool = False


@dataclass
class PromoCodeEntity:
    code: str
    discount_per_person: int
    is_active: bool = True


@dataclass
class FaqEntity:
    id: int | None
    button_title: str
    answer_html: str
    sort_order: int = 0


@dataclass
class PaymentWebhookResult:
    is_valid: bool
    booking_id: int | None = None
    status: str | None = None
    transaction_id: str | None = None
    amount: float | None = None
    currency: str | None = None
