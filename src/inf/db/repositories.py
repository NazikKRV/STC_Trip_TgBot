from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities import TourEntity, BookingEntity, BookingStatus
from src.inf.db.models import TourModel, BookingModel


class PostgresTourRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    def _to_entity(self, model: TourModel) -> TourEntity:
        return TourEntity(
            id=model.id,
            title=model.title,
            dates=model.dates,
            price=model.price,
            program_url=model.program_url,
            included_details=model.included_details,
            payment_deadline=model.payment_deadline,
            chat_link=model.chat_link,
            max_seats=model.max_seats,
            is_active=model.is_active,
        )

    async def get_active_tours(self) -> list[TourEntity]:
        stmt = select(TourModel).where(TourModel.is_active.is_(True))
        result = await self._session.execute(stmt)
        return [self._to_entity(row) for row in result.scalars().all()]

    async def get_by_id(self, tour_id: int) -> TourEntity | None:
        model = await self._session.get(TourModel, tour_id)
        return self._to_entity(model) if model else None

    async def create_seed_tour(self, tour: TourEntity) -> TourEntity:
        model = TourModel(
            title=tour.title,
            dates=tour.dates,
            price=tour.price,
            program_url=tour.program_url,
            included_details=tour.included_details,
            payment_deadline=tour.payment_deadline,
            chat_link=tour.chat_link,
            max_seats=tour.max_seats,
            is_active=tour.is_active,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_entity(model)


class PostgresBookingRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    def _to_entity(self, model: BookingModel) -> BookingEntity:
        return BookingEntity(
            id=model.id,
            user_telegram_id=model.user_telegram_id,
            tour_id=model.tour_id,
            full_name=model.full_name,
            phone=model.phone,
            age=model.age,
            tickets_count=model.tickets_count,
            other_participants=model.other_participants,
            amount=model.amount,
            status=BookingStatus(model.status),
            transaction_id=model.transaction_id,
        )

    async def create(self, booking: BookingEntity) -> BookingEntity:
        model = BookingModel(
            user_telegram_id=booking.user_telegram_id,
            tour_id=booking.tour_id,
            full_name=booking.full_name,
            phone=booking.phone,
            age=booking.age,
            tickets_count=booking.tickets_count,
            other_participants=booking.other_participants,
            amount=booking.amount,
            status=booking.status.value,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def get_booked_seats_count(self, tour_id: int) -> int:
        stmt = select(func.coalesce(func.sum(BookingModel.tickets_count), 0)).where(
            BookingModel.tour_id == tour_id,
            BookingModel.status == BookingStatus.CONFIRMED.value,
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def get_by_id(self, booking_id: int) -> BookingEntity | None:
        model = await self._session.get(BookingModel, booking_id)
        return self._to_entity(model) if model else None

    async def update_status(
        self, booking_id: int, status: BookingStatus, transaction_id: str | None = None
    ) -> BookingEntity | None:
        model = await self._session.get(BookingModel, booking_id)
        if not model:
            return None
        model.status = status.value
        if transaction_id:
            model.transaction_id = transaction_id
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def get_confirmed_by_tour(self, tour_id: int) -> list[BookingEntity]:
        stmt = select(BookingModel).where(
            BookingModel.tour_id == tour_id,
            BookingModel.status == BookingStatus.CONFIRMED.value,
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(row) for row in result.scalars().all()]
