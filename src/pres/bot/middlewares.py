from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from src.domain.interfaces import IPaymentGateway, INotificationService
from src.inf.db.repositories import (
    PostgresTourRepository,
    PostgresBookingRepository,
)
from src.app.services import TourService, BookingService


class DependencyInjectionMiddleware(BaseMiddleware):
    def __init__(
        self,
        session_pool: async_sessionmaker[AsyncSession],
        payment_gateway: IPaymentGateway,
        notifier: INotificationService,
    ):
        self._session_pool = session_pool
        self._payment_gateway = payment_gateway
        self._notifier = notifier

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with self._session_pool() as session:
            tour_repo = PostgresTourRepository(session)
            booking_repo = PostgresBookingRepository(session)

            data["tour_service"] = TourService(tour_repo, booking_repo)
            data["booking_service"] = BookingService(
                booking_repo=booking_repo,
                tour_repo=tour_repo,
                payment_gateway=self._payment_gateway,
                notifier=self._notifier,
            )
            return await handler(event, data)