from datetime import datetime, timedelta, timezone
import re
from sqlalchemy import select, func, update, delete, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities import (
    TourEntity,
    BookingEntity,
    BookingStatus,
    UserEntity,
    PromoCodeEntity,
    FaqEntity,
)
from src.inf.db.models import (
    TourModel,
    BookingModel,
    UserModel,
    PromoCodeModel,
    FaqModel,
)

PENDING_HOLD_MINUTES = 15


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
            duration_days=model.duration_days or 1,
            is_active=model.is_active,
        )

    async def get_active_tours(self) -> list[TourEntity]:
        stmt = (
            select(TourModel)
            .where(TourModel.is_active.is_(True))
            .order_by(TourModel.id)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(row) for row in result.scalars().all()]

    async def get_by_id(
        self, tour_id: int, for_update: bool = False
    ) -> TourEntity | None:
        stmt = select(TourModel).where(TourModel.id == tour_id)
        if for_update:
            stmt = stmt.with_for_update()
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
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
            duration_days=tour.duration_days,
            is_active=tour.is_active,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def sync_tours(self, tours: list[TourEntity]) -> int:
        def _short_date(d: str) -> str:
            base = re.sub(r"\s*\(.*?\)", "", str(d or "")).strip()
            return re.sub(r"\s+", " ", base).lower()

        all_res = await self._session.execute(select(TourModel))
        all_existing = list(all_res.scalars().all())
        for m in all_existing:
            m.is_active = False

        synced_count = 0
        for t in tours:
            t_title_norm = re.sub(r"\s+", " ", t.title.strip()).lower()
            t_short_date = _short_date(t.dates)

            existing = next(
                (
                    m
                    for m in all_existing
                    if m.title == t.title and m.dates == t.dates
                ),
                None,
            )
            if not existing:
                existing = next(
                    (
                        m
                        for m in all_existing
                        if re.sub(r"\s+", " ", m.title.strip()).lower() == t_title_norm
                        and _short_date(m.dates) == t_short_date
                    ),
                    None,
                )

            if existing:
                existing.title = t.title
                existing.dates = t.dates
                existing.price = t.price
                existing.program_url = t.program_url
                existing.included_details = t.included_details
                existing.payment_deadline = t.payment_deadline
                existing.chat_link = t.chat_link
                existing.max_seats = t.max_seats
                existing.duration_days = t.duration_days
                existing.is_active = t.is_active
            else:
                new_tour = TourModel(
                    title=t.title,
                    dates=t.dates,
                    price=t.price,
                    program_url=t.program_url,
                    included_details=t.included_details,
                    payment_deadline=t.payment_deadline,
                    chat_link=t.chat_link,
                    max_seats=t.max_seats,
                    duration_days=t.duration_days,
                    is_active=t.is_active,
                )
                self._session.add(new_tour)
                all_existing.append(new_tour)
            if t.is_active:
                synced_count += 1

        await self._session.commit()
        return synced_count


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
            notes=model.notes or "немає",
            discount_info=model.discount_info or "немає",
            username=model.username,
            created_at=model.created_at,
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
            notes=booking.notes,
            discount_info=booking.discount_info,
            username=booking.username,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def get_booked_seats_count(
        self, tour_id: int, include_pending: bool = True
    ) -> int:
        hold_threshold = datetime.now(timezone.utc) - timedelta(
            minutes=PENDING_HOLD_MINUTES
        )
        if include_pending:
            status_condition = or_(
                BookingModel.status == BookingStatus.CONFIRMED.value,
                BookingModel.status == BookingStatus.WAITING_RECEIPT.value,
                and_(
                    BookingModel.status == BookingStatus.PENDING.value,
                    BookingModel.created_at >= hold_threshold,
                ),
            )
        else:
            status_condition = (
                BookingModel.status == BookingStatus.CONFIRMED.value
            )

        stmt = select(func.coalesce(func.sum(BookingModel.tickets_count), 0)).where(
            BookingModel.tour_id == tour_id,
            status_condition,
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def cancel_user_pending_bookings(
        self, user_telegram_id: int, tour_id: int
    ) -> None:
        stmt = (
            update(BookingModel)
            .where(
                BookingModel.user_telegram_id == user_telegram_id,
                BookingModel.tour_id == tour_id,
                BookingModel.status == BookingStatus.PENDING.value,
            )
            .values(status=BookingStatus.FAILED.value)
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def get_user_confirmed_bookings_count(self, user_telegram_id: int) -> int:
        stmt = select(func.count(BookingModel.id)).where(
            BookingModel.user_telegram_id == user_telegram_id,
            BookingModel.status == BookingStatus.CONFIRMED.value,
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def get_by_id(self, booking_id: int) -> BookingEntity | None:
        model = await self._session.get(BookingModel, booking_id)
        return self._to_entity(model) if model else None

    async def get_latest_pending_by_user(
        self, user_telegram_id: int
    ) -> BookingEntity | None:
        stmt = (
            select(BookingModel)
            .where(
                BookingModel.user_telegram_id == user_telegram_id,
                BookingModel.status == BookingStatus.PENDING.value,
            )
            .order_by(BookingModel.id.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def update_status(
        self,
        booking_id: int,
        status: BookingStatus,
        transaction_id: str | None = None,
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

    async def update_amount_and_status(
        self,
        booking_id: int,
        amount: int,
        discount_info: str,
        status: BookingStatus,
    ) -> BookingEntity | None:
        model = await self._session.get(BookingModel, booking_id)
        if not model:
            return None
        model.amount = amount
        model.discount_info = discount_info
        model.status = status.value
        model.created_at = datetime.now(timezone.utc)
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


class PostgresUserRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    def _to_entity(self, model: UserModel) -> UserEntity:
        return UserEntity(
            telegram_id=model.telegram_id,
            full_name=model.full_name,
            phone=model.phone,
            username=model.username,
            is_loyal=model.is_loyal,
            loyal_request_pending=model.loyal_request_pending,
        )

    async def get_or_create(
        self,
        telegram_id: int,
        username: str | None = None,
        full_name: str | None = None,
        phone: str | None = None,
    ) -> UserEntity:
        model = await self._session.get(UserModel, telegram_id)
        if not model:
            model = UserModel(
                telegram_id=telegram_id,
                username=username,
                full_name=full_name,
                phone=phone,
                is_loyal=False,
                loyal_request_pending=False,
            )
            self._session.add(model)
        else:
            if username:
                model.username = username
            if full_name:
                model.full_name = full_name
            if phone:
                model.phone = phone
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def set_loyal_status(
        self, telegram_id: int, is_loyal: bool, pending: bool = False
    ) -> UserEntity | None:
        model = await self._session.get(UserModel, telegram_id)
        if not model:
            model = UserModel(
                telegram_id=telegram_id,
                is_loyal=is_loyal,
                loyal_request_pending=pending,
            )
            self._session.add(model)
        else:
            model.is_loyal = is_loyal
            model.loyal_request_pending = pending
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_entity(model)


class PostgresPromoCodeRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    def _to_entity(self, model: PromoCodeModel) -> PromoCodeEntity:
        return PromoCodeEntity(
            code=model.code,
            discount_per_person=model.discount_per_person,
            is_active=model.is_active,
        )

    async def get_active_by_code(self, code: str) -> PromoCodeEntity | None:
        normalized = code.strip().upper()
        model = await self._session.get(PromoCodeModel, normalized)
        if model and model.is_active:
            return self._to_entity(model)
        return None

    async def upsert_promo(self, promo: PromoCodeEntity) -> PromoCodeEntity:
        normalized = promo.code.strip().upper()
        model = await self._session.get(PromoCodeModel, normalized)
        if model:
            model.discount_per_person = promo.discount_per_person
            model.is_active = promo.is_active
        else:
            model = PromoCodeModel(
                code=normalized,
                discount_per_person=promo.discount_per_person,
                is_active=promo.is_active,
            )
            self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def sync_promos(self, promos: list[PromoCodeEntity]) -> int:
        await self._session.execute(update(PromoCodeModel).values(is_active=False))
        count = 0
        for p in promos:
            await self.upsert_promo(p)
            if p.is_active:
                count += 1
        return count


class PostgresFaqRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    def _to_entity(self, model: FaqModel) -> FaqEntity:
        return FaqEntity(
            id=model.id,
            button_title=model.button_title,
            answer_html=model.answer_html,
            sort_order=model.sort_order,
        )

    async def get_all(self) -> list[FaqEntity]:
        stmt = select(FaqModel).order_by(FaqModel.sort_order, FaqModel.id)
        result = await self._session.execute(stmt)
        return [self._to_entity(row) for row in result.scalars().all()]

    async def sync_faqs(self, faqs: list[FaqEntity]) -> int:
        await self._session.execute(delete(FaqModel))
        for idx, f in enumerate(faqs):
            self._session.add(
                FaqModel(
                    button_title=f.button_title,
                    answer_html=f.answer_html,
                    sort_order=idx,
                )
            )
        await self._session.commit()
        return len(faqs)
