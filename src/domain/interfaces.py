from typing import Protocol
from src.domain.entities import (
    TourEntity,
    BookingEntity,
    BookingStatus,
    UserEntity,
    PromoCodeEntity,
    FaqEntity,
    PaymentWebhookResult,
)


class ITourRepository(Protocol):
    async def get_active_tours(self) -> list[TourEntity]: ...
    async def get_by_id(
        self, tour_id: int, for_update: bool = False
    ) -> TourEntity | None: ...
    async def create_seed_tour(self, tour: TourEntity) -> TourEntity: ...
    async def sync_tours(self, tours: list[TourEntity]) -> int: ...


class IBookingRepository(Protocol):
    async def create(self, booking: BookingEntity) -> BookingEntity: ...
    async def get_by_id(self, booking_id: int) -> BookingEntity | None: ...
    async def update_status(
        self,
        booking_id: int,
        status: BookingStatus,
        transaction_id: str | None = None,
    ) -> BookingEntity | None: ...
    async def update_amount_and_status(
        self,
        booking_id: int,
        amount: int,
        discount_info: str,
        status: BookingStatus,
    ) -> BookingEntity | None: ...
    async def cancel_user_pending_bookings(
        self, user_telegram_id: int, tour_id: int
    ) -> None: ...

    async def get_confirmed_by_tour(self, tour_id: int) -> list[BookingEntity]: ...
    async def get_booked_seats_count(
        self, tour_id: int, include_pending: bool = True
    ) -> int: ...
    async def get_user_confirmed_bookings_count(self, user_telegram_id: int) -> int: ...


class IUserRepository(Protocol):
    async def get_or_create(
        self,
        telegram_id: int,
        username: str | None = None,
        full_name: str | None = None,
        phone: str | None = None,
    ) -> UserEntity: ...
    async def set_loyal_status(
        self, telegram_id: int, is_loyal: bool, pending: bool = False
    ) -> UserEntity | None: ...


class IPromoCodeRepository(Protocol):
    async def get_active_by_code(self, code: str) -> PromoCodeEntity | None: ...
    async def upsert_promo(self, promo: PromoCodeEntity) -> PromoCodeEntity: ...
    async def sync_promos(self, promos: list[PromoCodeEntity]) -> int: ...


class IFaqRepository(Protocol):
    async def get_all(self) -> list[FaqEntity]: ...
    async def sync_faqs(self, faqs: list[FaqEntity]) -> int: ...


class IPaymentGateway(Protocol):
    def generate_checkout_url(
        self, booking_id: int, amount: int, description: str
    ) -> str: ...

    def parse_and_verify_webhook(
        self, data: str, signature: str
    ) -> PaymentWebhookResult: ...


class INotificationService(Protocol):
    async def notify_booking_confirmed(
        self, booking: BookingEntity, tour: TourEntity
    ) -> None: ...

    async def notify_payment_failed(self, booking: BookingEntity) -> None: ...

    async def notify_admin_error(self, message: str) -> None: ...
