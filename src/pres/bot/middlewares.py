from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from src.config import settings
from src.domain.interfaces import IPaymentGateway, INotificationService
from src.inf.db.repositories import (
    PostgresTourRepository,
    PostgresBookingRepository,
    PostgresUserRepository,
    PostgresPromoCodeRepository,
    PostgresFaqRepository,
)
from src.inf.sheets.google_sheets import GoogleSheetsService
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
        self._sheets_service = GoogleSheetsService(
            credentials_path=settings.google_credentials_path,
            sheet_id=settings.google_sheet_id,
        )

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with self._session_pool() as session:
            tour_repo = PostgresTourRepository(session)
            booking_repo = PostgresBookingRepository(session)
            user_repo = PostgresUserRepository(session)
            promo_repo = PostgresPromoCodeRepository(session)
            faq_repo = PostgresFaqRepository(session)

            data["tour_service"] = TourService(
                tour_repo=tour_repo,
                booking_repo=booking_repo,
                faq_repo=faq_repo,
                promo_repo=promo_repo,
            )
            data["booking_service"] = BookingService(
                booking_repo=booking_repo,
                tour_repo=tour_repo,
                payment_gateway=self._payment_gateway,
                notifier=self._notifier,
                user_repo=user_repo,
                promo_repo=promo_repo,
                sheets_service=self._sheets_service,
            )
            return await handler(event, data)
