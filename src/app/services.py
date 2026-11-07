import logging
from src.domain.entities import TourEntity, BookingEntity, BookingStatus
from src.domain.interfaces import (
    ITourRepository,
    IBookingRepository,
    IPaymentGateway,
    INotificationService,
)

logger = logging.getLogger(__name__)


class TourService:
    def __init__(
        self,
        tour_repo: ITourRepository,
        booking_repo: IBookingRepository | None = None,
    ):
        self._tour_repo = tour_repo
        self._booking_repo = booking_repo

    async def list_available_tours(self) -> list[TourEntity]:
        return await self._tour_repo.get_active_tours()

    async def get_tour(self, tour_id: int) -> TourEntity | None:
        return await self._tour_repo.get_by_id(tour_id)

    async def sync_from_sheets(self, sheets_service) -> int:
        tours = await sheets_service.fetch_tours_from_sheet()
        return await self._tour_repo.sync_tours(tours)

    async def get_remaining_seats(self, tour_id: int) -> int:
        tour = await self._tour_repo.get_by_id(tour_id)
        if not tour or not tour.is_active or not self._booking_repo:
            return 0
        booked = await self._booking_repo.get_booked_seats_count(
            tour_id, include_pending=True
        )
        return max(0, tour.max_seats - booked)

    def format_marketing_seats_text(self, real_left: int) -> str:
        """Маркетинговий трюк із дефіцитом місць."""
        if real_left == 0:
            return "❌ Місць більше немає (Sold Out)"
        elif real_left > 12:
            return "🔥 Залишилось +-10 вільних місць!"
        else:
            return f"🚨 Поспішайте! Залишилось всього {real_left} місць!"

    async def seed_demo_tour_if_empty(self) -> None:
        tours = await self._tour_repo.get_active_tours()
        if not tours:
            demo_tour = TourEntity(
                id=None,
                title="НЕЙМОВІРНА БОРЖАВА 🏔🍁",
                dates="11 жовтня (07:00-22:30)",
                price=1200,
                program_url="https://telegra.ph/CHORNICHNA-BORZHAVA-POH%D0%86D-HREBTOM-z-STC-07-24",
                included_details=(
                    "✅ Проїзд автобусом євро-класу (аудіо, кондиціонер)\n"
                    "✅ Супровід тімлідера стк;\n"
                    "✅ Екскурсійне обслуговування протягом туру;\n"
                    "✅ Фото-звіт;\n"
                    "✅ Розіграш призів."
                ),
                payment_deadline="сьогодні 22:00",
                chat_link="https://t.me/+example_borzhava_chat",
                max_seats=59,
                is_active=True,
            )
            await self._tour_repo.create_seed_tour(demo_tour)


class BookingService:
    def __init__(
        self,
        booking_repo: IBookingRepository,
        tour_repo: ITourRepository,
        payment_gateway: IPaymentGateway,
        notifier: INotificationService,
        sheets_service=None,
    ):
        self._booking_repo = booking_repo
        self._tour_repo = tour_repo
        self._payment_gateway = payment_gateway
        self._notifier = notifier
        self._sheets_service = sheets_service

    async def create_booking_with_payment_link(
        self,
        user_telegram_id: int,
        tour_id: int,
        full_name: str,
        phone: str,
        age: int,
        tickets_count: int,
        other_participants: str,
    ) -> tuple[BookingEntity, TourEntity, str]:
        # Блокуємо рядок туру (SELECT ... FOR UPDATE) на час перевірки місць та створення бронювання
        tour = await self._tour_repo.get_by_id(tour_id, for_update=True)
        if not tour or not tour.is_active:
            raise ValueError("Тур не знайдено або він більше не активний")

        booked_seats = await self._booking_repo.get_booked_seats_count(
            tour_id, include_pending=True
        )
        real_left = max(0, tour.max_seats - booked_seats)
        if tickets_count > real_left:
            raise ValueError(f"Недостатньо місць. Доступно лише: {real_left}")

        total_amount = tour.price * tickets_count

        booking = BookingEntity(
            id=None,
            user_telegram_id=user_telegram_id,
            tour_id=tour_id,
            full_name=full_name,
            phone=phone,
            age=age,
            tickets_count=tickets_count,
            other_participants=other_participants,
            amount=total_amount,
        )
        saved_booking = await self._booking_repo.create(booking)

        payment_url = self._payment_gateway.generate_checkout_url(
            booking_id=saved_booking.id,
            amount=saved_booking.amount,
            description=f"Оплата за тур «{tour.title}» ({tickets_count} місць) | {full_name}",
        )
        return saved_booking, tour, payment_url

    async def process_payment_webhook(self, data: str, signature: str) -> bool:
        result = self._payment_gateway.parse_and_verify_webhook(data, signature)

        if not result.is_valid or not result.booking_id:
            return False

        booking = await self._booking_repo.get_by_id(result.booking_id)
        if not booking:
            return False

        if booking.status == BookingStatus.CONFIRMED:
            return True

        if result.status in ("success", "sandbox"):
            tour = await self._tour_repo.get_by_id(booking.tour_id, for_update=True)
            confirmed_before = await self._booking_repo.get_booked_seats_count(
                booking.tour_id, include_pending=False
            )

            updated_booking = await self._booking_repo.update_status(
                booking_id=result.booking_id,
                status=BookingStatus.CONFIRMED,
                transaction_id=result.transaction_id,
            )

            if updated_booking and tour:
                if confirmed_before + updated_booking.tickets_count > tour.max_seats:
                    await self._notifier.notify_admin_error(
                        f"Увага! Перевищено ліміт місць (овербукінг) у турі «{tour.title}» "
                        f"після оплати бронювання #{updated_booking.id} ({updated_booking.full_name}). "
                        f"Оплачено місць: {confirmed_before + updated_booking.tickets_count} із {tour.max_seats}."
                    )

                await self._notifier.notify_booking_confirmed(updated_booking, tour)

                if self._sheets_service:
                    try:
                        await self._sheets_service.append_paid_booking(
                            tour, updated_booking
                        )
                    except Exception as e:
                        logger.exception("Помилка запису в Google Sheets")
                        await self._notifier.notify_admin_error(
                            f"Не вдалося записати бронювання #{updated_booking.id} "
                            f"({updated_booking.full_name}) у Google Sheets: {e}"
                        )
            return True

        if result.status in ("failure", "error", "reversed", "unsubscribed"):
            if booking.status != BookingStatus.FAILED:
                await self._booking_repo.update_status(
                    booking_id=result.booking_id,
                    status=BookingStatus.FAILED,
                    transaction_id=result.transaction_id,
                )
                await self._notifier.notify_payment_failed(booking)
            return True

        # Проміжні статуси LiqPay (processing, 3ds_verify, wait_accept тощо)
        return True

    async def get_group_list(self, tour_id: int) -> list[BookingEntity]:
        return await self._booking_repo.get_confirmed_by_tour(tour_id)
