import logging
from src.domain.entities import (
    TourEntity,
    BookingEntity,
    BookingStatus,
    PromoCodeEntity,
    FaqEntity,
    UserEntity,
)
from src.domain.interfaces import (
    ITourRepository,
    IBookingRepository,
    IUserRepository,
    IPromoCodeRepository,
    IFaqRepository,
    IPaymentGateway,
    INotificationService,
)
from src.domain.default_faqs import DEFAULT_FAQS

logger = logging.getLogger(__name__)


class TourService:
    def __init__(
        self,
        tour_repo: ITourRepository,
        booking_repo: IBookingRepository | None = None,
        faq_repo: IFaqRepository | None = None,
        promo_repo: IPromoCodeRepository | None = None,
    ):
        self._tour_repo = tour_repo
        self._booking_repo = booking_repo
        self._faq_repo = faq_repo
        self._promo_repo = promo_repo

    async def list_available_tours(self) -> list[TourEntity]:
        return await self._tour_repo.get_active_tours()

    async def get_tour(self, tour_id: int) -> TourEntity | None:
        return await self._tour_repo.get_by_id(tour_id)

    async def list_faqs(self) -> list[FaqEntity]:
        if not self._faq_repo:
            return DEFAULT_FAQS
        faqs = await self._faq_repo.get_all()
        return faqs if faqs else DEFAULT_FAQS

    async def sync_from_sheets(self, sheets_service) -> tuple[int, int, int]:
        tours = await sheets_service.fetch_tours_from_sheet()
        tours_count = await self._tour_repo.sync_tours(tours)

        faqs_count = len(DEFAULT_FAQS)
        if self._faq_repo:
            faqs = await sheets_service.sync_faqs_with_sheet(DEFAULT_FAQS)
            faqs_count = await self._faq_repo.sync_faqs(faqs)

        promos_count = 0
        if self._promo_repo:
            promos = await sheets_service.sync_promos_with_sheet()
            promos_count = await self._promo_repo.sync_promos(promos)

        return tours_count, faqs_count, promos_count

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

    async def seed_defaults_if_empty(self) -> None:
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
                duration_days=1,
                is_active=True,
            )
            await self._tour_repo.create_seed_tour(demo_tour)

        if self._faq_repo:
            existing_faqs = await self._faq_repo.get_all()
            if len(existing_faqs) < len(DEFAULT_FAQS):
                await self._faq_repo.sync_faqs(DEFAULT_FAQS)

        if self._promo_repo:
            existing_promo = await self._promo_repo.get_active_by_code("OLDFRIEND")
            if not existing_promo:
                await self._promo_repo.upsert_promo(
                    PromoCodeEntity(
                        code="OLDFRIEND",
                        discount_per_person=50,
                        is_active=True,
                    )
                )


class BookingService:
    def __init__(
        self,
        booking_repo: IBookingRepository,
        tour_repo: ITourRepository,
        payment_gateway: IPaymentGateway,
        notifier: INotificationService,
        user_repo: IUserRepository | None = None,
        promo_repo: IPromoCodeRepository | None = None,
        sheets_service=None,
    ):
        self._booking_repo = booking_repo
        self._tour_repo = tour_repo
        self._payment_gateway = payment_gateway
        self._notifier = notifier
        self._user_repo = user_repo
        self._promo_repo = promo_repo
        self._sheets_service = sheets_service

    async def is_user_loyal(self, user_telegram_id: int) -> bool:
        """Користувач є постійним клієнтом, якщо статус підтверджено менеджером АБО має >= 2 оплачених турів у боті."""
        if self._user_repo:
            user = await self._user_repo.get_or_create(user_telegram_id)
            if user.is_loyal:
                return True
        confirmed_count = await self._booking_repo.get_user_confirmed_bookings_count(
            user_telegram_id
        )
        return confirmed_count >= 2

    async def get_or_update_user(
        self,
        telegram_id: int,
        username: str | None = None,
        full_name: str | None = None,
        phone: str | None = None,
    ) -> UserEntity | None:
        if not self._user_repo:
            return None
        return await self._user_repo.get_or_create(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
            phone=phone,
        )

    async def set_loyal_status(
        self, telegram_id: int, is_loyal: bool, pending: bool = False
    ) -> UserEntity | None:
        if not self._user_repo:
            return None
        return await self._user_repo.set_loyal_status(
            telegram_id=telegram_id, is_loyal=is_loyal, pending=pending
        )

    async def validate_promo_code(self, code: str) -> PromoCodeEntity | None:
        if not self._promo_repo or not code:
            return None
        return await self._promo_repo.get_active_by_code(code)

    async def upsert_promo_code(
        self, code: str, discount_per_person: int
    ) -> PromoCodeEntity | None:
        if not self._promo_repo:
            return None
        return await self._promo_repo.upsert_promo(
            PromoCodeEntity(
                code=code.strip().upper(),
                discount_per_person=discount_per_person,
                is_active=True,
            )
        )

    def calculate_discount(
        self,
        tour: TourEntity,
        tickets_count: int,
        is_loyal: bool,
        ubd_children_count: int = 0,
        promo: PromoCodeEntity | None = None,
    ) -> tuple[int, int, str]:
        """
        Розраховує (final_amount, total_discount, discount_info).
        Правило: Знижки не сумуються між собою та з промокодами!
        Тарифи:
        - 1-денний тур: Постійні = -50/ос, Група 3-5 = -50/ос, Діти до 10р / УБД = -100/ос
        - 2/3-денний тур: Постійні = -150/ос, Група 3-5 = -150/ос, Діти до 10р / УБД = -200/ос
        """
        base_amount = tour.price * tickets_count
        is_multiday = (tour.duration_days or 1) >= 2

        std_rate = 150 if is_multiday else 50
        ubd_rate = 200 if is_multiday else 100

        ubd_count = min(max(0, ubd_children_count), tickets_count)
        regular_count = tickets_count - ubd_count

        # Якщо введено промокод — промокод не сумується з іншими знижками
        if promo:
            promo_discount = promo.discount_per_person * tickets_count
            parts = [
                f"Промокод {promo.code}: -{promo.discount_per_person} грн/ос (разом -{promo_discount} грн)"
            ]
            if ubd_count > 0:
                parts.append(f"[Позначка: УБД/Діти — {ubd_count} ос.]")
            final_amount = max(1, base_amount - promo_discount)
            return final_amount, promo_discount, " | ".join(parts)

        total_discount = 0
        parts: list[str] = []

        if ubd_count > 0:
            ubd_disc = ubd_count * ubd_rate
            total_discount += ubd_disc
            parts.append(f"УБД/Діти до 10р ({ubd_count} ос.): -{ubd_disc} грн")

        if regular_count > 0:
            if 3 <= tickets_count <= 5:
                reg_disc = regular_count * std_rate
                total_discount += reg_disc
                label = (
                    f"Постійний клієнт / Група 3-5 ос. ({regular_count} ос.): -{reg_disc} грн"
                    if is_loyal
                    else f"Група 3-5 ос. ({regular_count} ос.): -{reg_disc} грн"
                )
                parts.append(label)
            elif is_loyal:
                # Знижка постійного клієнта діє лише на самого замовника (1 особу)
                loyal_seats = min(1, regular_count)
                reg_disc = loyal_seats * std_rate
                total_discount += reg_disc
                parts.append(
                    f"Постійний клієнт ({loyal_seats} ос.): -{reg_disc} грн"
                )

        if total_discount == 0:
            return base_amount, 0, "немає"

        final_amount = max(1, base_amount - total_discount)
        return final_amount, total_discount, "; ".join(parts)

    async def create_booking_with_payment_link(
        self,
        user_telegram_id: int,
        tour_id: int,
        full_name: str,
        phone: str,
        age: int,
        tickets_count: int,
        other_participants: str,
        notes: str = "немає",
        ubd_children_count: int = 0,
        promo_code: str | None = None,
        username: str | None = None,
    ) -> tuple[BookingEntity, TourEntity, str]:
        tour = await self._tour_repo.get_by_id(tour_id, for_update=True)
        if not tour or not tour.is_active:
            raise ValueError("Тур не знайдено або він більше не активний")

        # Скасовуємо попередні неоплачені резерви цього ж користувача на цей тур,
        # щоб одна людина не могла штучно заблокувати всі місця в автобусі
        await self._booking_repo.cancel_user_pending_bookings(
            user_telegram_id, tour_id
        )

        booked_seats = await self._booking_repo.get_booked_seats_count(
            tour_id, include_pending=True
        )
        real_left = max(0, tour.max_seats - booked_seats)
        if tickets_count > real_left:
            raise ValueError(f"Недостатньо місць. Доступно лише: {real_left}")

        await self.get_or_update_user(
            telegram_id=user_telegram_id,
            username=username,
            full_name=full_name,
            phone=phone,
        )
        is_loyal = await self.is_user_loyal(user_telegram_id)
        promo = await self.validate_promo_code(promo_code) if promo_code else None

        final_amount, _, discount_info = self.calculate_discount(
            tour=tour,
            tickets_count=tickets_count,
            is_loyal=is_loyal,
            ubd_children_count=ubd_children_count,
            promo=promo,
        )

        booking = BookingEntity(
            id=None,
            user_telegram_id=user_telegram_id,
            tour_id=tour_id,
            full_name=full_name,
            phone=phone,
            age=age,
            tickets_count=tickets_count,
            other_participants=other_participants,
            amount=final_amount,
            status=BookingStatus.PENDING,
            notes=notes or "немає",
            discount_info=discount_info,
            username=username,
        )
        saved_booking = await self._booking_repo.create(booking)

        payment_url = self._payment_gateway.generate_checkout_url(
            booking_id=saved_booking.id,
            amount=saved_booking.amount,
            description=f"Оплата за тур «{tour.title}» ({tickets_count} місць) | {full_name}",
        )
        return saved_booking, tour, payment_url

    async def create_large_group_booking(
        self,
        user_telegram_id: int,
        tour_id: int,
        full_name: str,
        phone: str,
        age: int,
        tickets_count: int,
        other_participants: str,
        notes: str = "немає",
        username: str | None = None,
    ) -> tuple[BookingEntity, TourEntity]:
        tour = await self._tour_repo.get_by_id(tour_id, for_update=True)
        if not tour or not tour.is_active:
            raise ValueError("Тур не знайдено або він більше не активний")

        # Скасовуємо попередні неоплачені резерви цього ж користувача на цей тур,
        # щоб одна людина не могла штучно заблокувати всі місця в автобусі
        await self._booking_repo.cancel_user_pending_bookings(
            user_telegram_id, tour_id
        )

        booked_seats = await self._booking_repo.get_booked_seats_count(
            tour_id, include_pending=True
        )
        real_left = max(0, tour.max_seats - booked_seats)
        if tickets_count > real_left:
            raise ValueError(f"Недостатньо місць. Доступно лише: {real_left}")

        await self.get_or_update_user(
            telegram_id=user_telegram_id,
            username=username,
            full_name=full_name,
            phone=phone,
        )

        base_amount = tour.price * tickets_count
        booking = BookingEntity(
            id=None,
            user_telegram_id=user_telegram_id,
            tour_id=tour_id,
            full_name=full_name,
            phone=phone,
            age=age,
            tickets_count=tickets_count,
            other_participants=other_participants,
            amount=base_amount,
            status=BookingStatus.WAITING_MANAGER,
            notes=notes or "немає",
            discount_info="Велика група 6+ осіб (індивідуальний прорахунок)",
            username=username,
        )
        saved_booking = await self._booking_repo.create(booking)
        return saved_booking, tour

    async def set_custom_price_and_get_payment_url(
        self, booking_id: int, custom_amount: int
    ) -> tuple[BookingEntity, TourEntity, str] | None:
        booking = await self._booking_repo.get_by_id(booking_id)
        if not booking:
            return None
        tour = await self._tour_repo.get_by_id(booking.tour_id)
        if not tour:
            return None

        base_amount = tour.price * booking.tickets_count
        diff = max(0, base_amount - custom_amount)
        discount_info = (
            f"Індивідуальна знижка (група {booking.tickets_count} ос.): -{diff} грн"
            if diff > 0
            else "Індивідуальний тариф"
        )

        updated = await self._booking_repo.update_amount_and_status(
            booking_id=booking_id,
            amount=custom_amount,
            discount_info=discount_info,
            status=BookingStatus.PENDING,
        )
        if not updated:
            return None

        payment_url = self._payment_gateway.generate_checkout_url(
            booking_id=updated.id,
            amount=updated.amount,
            description=f"Оплата за тур «{tour.title}» ({updated.tickets_count} місць) | {updated.full_name}",
        )
        return updated, tour, payment_url

    async def get_booking_with_tour(
        self, booking_id: int
    ) -> tuple[BookingEntity, TourEntity] | None:
        booking = await self._booking_repo.get_by_id(booking_id)
        if not booking:
            return None
        tour = await self._tour_repo.get_by_id(booking.tour_id)
        if not tour:
            return None
        return booking, tour

    async def mark_receipt_submitted(
        self, booking_id: int | None, user_telegram_id: int
    ) -> tuple[BookingEntity, TourEntity] | None:
        booking = None
        if booking_id:
            booking = await self._booking_repo.get_by_id(booking_id)
            if booking and booking.user_telegram_id != user_telegram_id:
                booking = None
        if not booking or booking.status != BookingStatus.PENDING:
            booking = await self._booking_repo.get_latest_pending_by_user(
                user_telegram_id
            )
        if not booking:
            return None

        tour = await self._tour_repo.get_by_id(booking.tour_id)
        if not tour:
            return None

        updated = await self._booking_repo.update_status(
            booking_id=booking.id,
            status=BookingStatus.CONFIRMED,
            transaction_id="🌹",
        )
        if updated and self._sheets_service:
            try:
                await self._sheets_service.append_paid_booking(tour, updated)
            except Exception as e:
                logger.exception("Помилка запису в Google Sheets")
                await self._notifier.notify_admin_error(
                    f"Не вдалося записати бронювання #{updated.id} у Google Sheets: {e}"
                )
        return (updated, tour) if updated else None

    async def verify_receipt_by_manager(
        self, booking_id: int, is_approved: bool
    ) -> tuple[BookingEntity, TourEntity] | None:
        booking = await self._booking_repo.get_by_id(booking_id)
        if not booking:
            return None
        tour = await self._tour_repo.get_by_id(booking.tour_id)
        if not tour:
            return None

        mark = "✅" if is_approved else "❌"
        new_status = (
            BookingStatus.CONFIRMED if is_approved else BookingStatus.FAILED
        )

        updated = await self._booking_repo.update_status(
            booking_id=booking_id,
            status=new_status,
            transaction_id=mark,
        )
        if updated and self._sheets_service:
            try:
                await self._sheets_service.update_booking_payment_mark(
                    tour, updated, mark
                )
            except Exception as e:
                logger.exception("Помилка оновлення позначки в Google Sheets")
                await self._notifier.notify_admin_error(
                    f"Не вдалося оновити позначку {mark} для бронювання #{booking_id} у Google Sheets: {e}"
                )
        return (updated, tour) if updated else None

    async def confirm_booking_manually(
        self, booking_id: int, manager_tag: str
    ) -> tuple[BookingEntity, TourEntity] | None:
        booking = await self._booking_repo.get_by_id(booking_id)
        if not booking:
            return None
        tour = await self._tour_repo.get_by_id(booking.tour_id)
        if not tour:
            return None

        already_confirmed = booking.status == BookingStatus.CONFIRMED
        updated = await self._booking_repo.update_status(
            booking_id=booking_id,
            status=BookingStatus.CONFIRMED,
            transaction_id="✅",
        )
        if updated:
            if not already_confirmed:
                await self._notifier.notify_booking_confirmed(updated, tour)
            if self._sheets_service:
                try:
                    await self._sheets_service.update_booking_payment_mark(
                        tour, updated, "✅"
                    )
                except Exception as e:
                    logger.exception("Помилка запису в Google Sheets")
                    await self._notifier.notify_admin_error(
                        f"Не вдалося записати бронювання #{updated.id} у Google Sheets: {e}"
                    )
            return updated, tour
        return None

    async def cancel_booking_by_manager(
        self, booking_id: int
    ) -> BookingEntity | None:
        return await self._booking_repo.update_status(
            booking_id=booking_id, status=BookingStatus.FAILED
        )

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
            if result.currency and result.currency != "UAH":
                await self._notifier.notify_admin_error(
                    f"Підозрілий платіж для бронювання #{booking.id}: валюта {result.currency} замість UAH!"
                )
                return False

            if result.amount is not None and int(round(result.amount)) < booking.amount:
                await self._notifier.notify_admin_error(
                    f"Підозрілий платіж для бронювання #{booking.id}: сплачено {result.amount} грн замість {booking.amount} грн!"
                )
                return False

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

        return True

    async def get_group_list(self, tour_id: int) -> list[BookingEntity]:
        return await self._booking_repo.get_confirmed_by_tour(tour_id)
