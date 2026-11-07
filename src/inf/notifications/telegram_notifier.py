import html
import logging
from aiogram import Bot
from src.domain.entities import BookingEntity, TourEntity
from src.config import settings
from src.pres.bot.keyboards import get_main_menu_kb, get_managers_group_kb

logger = logging.getLogger(__name__)


class TelegramNotificationService:
    def __init__(self, bot: Bot):
        self._bot = bot

    async def notify_booking_confirmed(
        self, booking: BookingEntity, tour: TourEntity
    ) -> None:
        safe_title = html.escape(tour.title)
        safe_dates = html.escape(tour.dates)
        safe_name = html.escape(booking.full_name)
        safe_phone = html.escape(booking.phone)
        safe_others = html.escape(booking.other_participants)
        safe_notes = html.escape(booking.notes or "немає")
        safe_discounts = html.escape(booking.discount_info or "немає")
        safe_tx = html.escape(str(booking.transaction_id or "—"))
        user_tag = f" (@{html.escape(booking.username)})" if booking.username else ""

        # 1. Повідомлення туристу
        try:
            await self._bot.send_message(
                chat_id=booking.user_telegram_id,
                text=(
                    f"🎉 <b>Оплату успішно отримано!</b>\n\n"
                    f"Ваше місце в турі <b>{safe_title}</b> ({safe_dates}) офіційно заброньовано.\n"
                    f"Вас автоматично додано до списку групи ✅\n\n"
                    f"За 2 дні до виїзду бот надішле Вам сюди посилання на організаційний чат туру ❤️"
                ),
                parse_mode="HTML",
                reply_markup=get_main_menu_kb(),
            )
        except Exception:
            logger.exception(
                "Не вдалося надіслати підтвердження туристу %s (бронювання #%s)",
                booking.user_telegram_id,
                booking.id,
            )

        # 2. Сповіщення в групу менеджерів про нового оплаченого учасника
        try:
            await self._bot.send_message(
                chat_id=settings.admin_chat_id,
                text=(
                    f"💳 <b>Нова оплата (Бронювання #{booking.id})</b>\n"
                    f"🏔 Тур: <b>{safe_title}</b> ({safe_dates})\n"
                    f"👤 Турист: {safe_name}{user_tag}\n"
                    f"📞 Тел: {safe_phone} | Вік: {booking.age}\n"
                    f"🎟 Кількість місць: <b>{booking.tickets_count}</b>\n"
                    f"👥 Інші учасники: {safe_others}\n"
                    f"🏷 Знижки / Пільги: <b>{safe_discounts}</b>\n"
                    f"📝 Нотатка: <i>{safe_notes}</i>\n"
                    f"💰 Сплачено: <b>{booking.amount} грн</b>\n"
                    f"🧾 ID транзакції: <code>{safe_tx}</code>"
                ),
                parse_mode="HTML",
                reply_markup=get_managers_group_kb(),
            )
        except Exception:
            logger.exception(
                "Не вдалося надіслати сповіщення в групу менеджерів про бронювання #%s",
                booking.id,
            )

    async def notify_payment_failed(self, booking: BookingEntity) -> None:
        try:
            await self._bot.send_message(
                chat_id=booking.user_telegram_id,
                text=(
                    "❌ <b>Оплата не пройшла або була скасована.</b>\n"
                    "Ви можете спробувати оплатити ще раз за посиланням вище або звернутися "
                    f"до нашого менеджера: @{html.escape(settings.manager_username)}"
                ),
                parse_mode="HTML",
            )
        except Exception:
            logger.exception(
                "Не вдалося надіслати сповіщення про невдалу оплату туристу %s",
                booking.user_telegram_id,
            )

    async def notify_admin_error(self, message: str) -> None:
        try:
            await self._bot.send_message(
                chat_id=settings.admin_chat_id,
                text=f"⚠️ <b>Системне сповіщення:</b>\n{html.escape(message)}",
                parse_mode="HTML",
            )
        except Exception:
            logger.exception("Не вдалося надіслати системне сповіщення в групу менеджерів")
