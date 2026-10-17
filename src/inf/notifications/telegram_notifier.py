from aiogram import Bot
from src.domain.entities import BookingEntity, TourEntity
from src.config import settings


class TelegramNotificationService:
    def __init__(self, bot: Bot):
        self._bot = bot

    async def notify_booking_confirmed(
        self, booking: BookingEntity, tour: TourEntity
    ) -> None:
        # 1. Повідомлення туристу
        await self._bot.send_message(
            chat_id=booking.user_telegram_id,
            text=(
                f"🎉 <b>Оплату успішно отримано!</b>\n\n"
                f"Ваше місце в турі <b>{tour.title}</b> ({tour.dates}) офіційно заброньовано.\n"
                f"Вас автоматично додано до списку групи ✅\n\n"
                f"Перед виїздом бот надішле Вам сюди посилання на організаційний чат туру ❤️"
            ),
            parse_mode="HTML",
        )

        # 2. Сповіщення адміну (Тарасу) про нового оплаченого учасника
        await self._bot.send_message(
            chat_id=settings.admin_chat_id,
            text=(
                f"💳 <b>Автоматична оплата (Бронювання #{booking.id})</b>\n"
                f"🏔 Тур: {tour.title}\n"
                f"👤 Турист: {booking.full_name}\n"
                f"📞 Тел: {booking.phone} | Вік: {booking.age}\n"
                f"🎟 Кількість місць: <b>{booking.tickets_count}</b>\n"
                f"👥 Інші учасники: {booking.other_participants}\n"
                f"💰 Сума: {booking.amount} грн\n"
                f"🧾 ID транзакції ПриватБанку: <code>{booking.transaction_id}</code>"
            ),
            parse_mode="HTML",
        )

    async def notify_payment_failed(self, booking: BookingEntity) -> None:
        await self._bot.send_message(
            chat_id=booking.user_telegram_id,
            text=(
                "❌ <b>Оплата не пройшла або була скасована.</b>\n"
                "Ви можете спробувати оплатити ще раз за посиланням вище або звернутися "
                f"до нашого менеджера: @{settings.manager_username}"
            ),
            parse_mode="HTML",
        )
