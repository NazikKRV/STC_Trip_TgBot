from typing import Protocol
from src.domain.entities import (
    TourEntity,
    BookingEntity,
    BookingStatus,
    PaymentWebhookResult,
)


class ITourRepository(Protocol):
    async def get_active_tours(self) -> list[TourEntity]: ...
    async def get_by_id(self, tour_id: int, for_update: bool = False) -> TourEntity | None: ...
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

    async def get_confirmed_by_tour(self, tour_id: int) -> list[BookingEntity]: ...
    async def get_booked_seats_count(
        self, tour_id: int, include_pending: bool = True
    ) -> int: ...


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
