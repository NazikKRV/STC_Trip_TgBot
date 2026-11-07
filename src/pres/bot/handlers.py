import asyncio
import html
import logging
import re
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from src.config import settings
from src.app.services import TourService, BookingService
from src.pres.bot.states import BookingForm
from src.pres.bot.keyboards import (
    get_main_menu_kb,
    get_tours_kb,
    get_tour_action_kb,
    get_terms_agreement_kb,
    get_payment_kb,
    get_cancel_kb,
    get_phone_kb,
    get_faq_menu_kb,
    get_faq_back_kb,
    get_admin_panel_kb,
    get_admin_tour_kb,
    get_admin_confirm_chat_kb,
)

logger = logging.getLogger(__name__)
router = Router()

# Повний список кодів українських мобільних та фіксованих операторів (2 цифри після +380)
UA_OPERATOR_CODES = {
    "39", "50", "63", "66", "67", "68", "73", "75", "77",
    "89", "91", "92", "93", "94", "95", "96", "97", "98", "99",
}


def normalize_phone_number(raw_phone: str) -> str | None:
    """
    Приймає телефон у будь-якому зручному форматі:
    - 097 123 45 67, 098-123-45-67, (067)1234567, 0501234567, 063...
    - +380971234567, 380971234567, 80971234567
    - 971234567 (9 цифр без нуля)
    - Міжнародні номери у форматі +48..., +49... (10-15 цифр)
    Повертає нормалізований номер у форматі +380XXXXXXXXX (або +XXXXXXXXXXX) чи None.
    """
    cleaned = re.sub(r"[\s\-\(\)\.]", "", raw_phone.strip())
    has_plus = cleaned.startswith("+")
    digits = re.sub(r"\D", "", cleaned)

    # Українські формати:
    if len(digits) == 12 and digits.startswith("380"):
        op_code = digits[3:5]
        if op_code in UA_OPERATOR_CODES:
            return f"+{digits}"
    elif len(digits) == 11 and digits.startswith("80"):
        op_code = digits[2:4]
        if op_code in UA_OPERATOR_CODES:
            return f"+3{digits}"
    elif len(digits) == 10 and digits.startswith("0"):
        op_code = digits[1:3]
        if op_code in UA_OPERATOR_CODES:
            return f"+38{digits}"
    elif len(digits) == 9 and not has_plus:
        op_code = digits[0:2]
        if op_code in UA_OPERATOR_CODES:
            return f"+380{digits}"

    # Підтримка міжнародних номерів (якщо клієнт із закордонною SIM-картою, напр. +48...)
    if has_plus and 10 <= len(digits) <= 15 and not digits.startswith("380"):
        return f"+{digits}"

    return None


def is_admin_user(user_id: int | None) -> bool:
    return user_id is not None and user_id == settings.admin_chat_id


FAQ_DATA: dict[str, tuple[str, str]] = {
    "booking": (
        "🎟 Як відбувається бронювання та оплата?",
        "<b>🎟 Як відбувається бронювання та оплата?</b>\n\n"
        "1. Ви обираєте бажаний тур у меню <b>«🏔 Обрати тур»</b>.\n"
        "2. Заповнюєте коротку анкету (ПІБ, телефон, вік та кількість місць).\n"
        "3. Бот генерує персональне посилання на безпечну оплату через <b>ПриватБанк (LiqPay)</b> (підтримується Apple Pay, Google Pay та оплата карткою будь-якого банку).\n"
        "4. Одразу після оплати місце закріплюється за вами автоматично, а квиток надходить у цей чат ❤️",
    ),
    "group": (
        "👥 Як забронювати місця для компанії/друзів?",
        "<b>👥 Як забронювати місця для компанії або друзів?</b>\n\n"
        "Під час заповнення анкети бот запитає: <i>«Скільки всього місць ви хочете забронювати?»</i>.\n\n"
        "Просто введіть потрібну цифру (наприклад, 2, 3 або більше) та одним повідомленням вкажіть ПІБ і вік ваших друзів. Ви зможете оплатити всі квитки одним платежем.",
    ),
    "refund": (
        "🔄 Що робити, якщо плани змінилися (Повернення)?",
        "<b>🔄 Що робити, якщо плани змінилися?</b>\n\n"
        "Ми розуміємо, що обставини бувають різними. Умови повернення коштів залежать від того, за скільки днів до виїзду ви повідомляєте про скасування, оскільки ми заздалегідь бронюємо транспорт та супутні послуги.\n\n"
        f"📄 Детальні правила прописані у документі: <a href='{settings.refund_policy_url}'>Умови повернення коштів</a>.\n"
        f"Для оформлення повернення або заміни учасника напишіть нашому менеджеру: @{settings.manager_username}",
    ),
    "chat": (
        "🚌 Коли я отримаю посилання на чат туру?",
        "<b>🚌 Коли я отримаю посилання на організаційний чат?</b>\n\n"
        "Напередодні виїзду ми формуємо спільний Telegram-чат для всіх учасників конкретного туру та тімлідера.\n\n"
        "Бот автоматично надішле вам запрошення в особисті повідомлення, де буде вся детальна інформація: точний час, геолокація місця збору, контакти супроводжуючого та відповіді на організаційні питання.",
    ),
    "items": (
        "🎒 Що взяти з собою в поїздку?",
        "<b>🎒 Що варто взяти з собою в тур?</b>\n\n"
        "• Паспорт або документи у застосунку «Дія»;\n"
        "• Зручне взуття (особливо для гірських маршрутів) та одяг по погоді;\n"
        "• Дощовик та змінний комплект речей про всяк випадок;\n"
        "• Перекус у дорогу, воду та термос із теплим чаєм;\n"
        "• Павербанк для телефону та індивідуальну аптечку;\n"
        "• Готівку на особисті витрати (сувеніри, колиби, вхідні квитки).\n\n"
        "<i>Точний список рекомендацій під конкретний маршрут завжди вказаний у детальній програмі туру!</i>",
    ),
}

FAQ_MAIN_TEXT = (
    "📌 <b>Корисна інформація та Поширені питання (FAQ)</b>\n\n"
    f"📃 Договір публічної оферти: {settings.public_offer_url}\n"
    f"📃 Опис умов повернення коштів: {settings.refund_policy_url}\n\n"
    "👇 <b>Оберіть питання зі списку нижче, щоб переглянути відповідь:</b>"
)


@router.message(CommandStart(), StateFilter("*"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id if message.from_user else None
    first_name = message.from_user.first_name if message.from_user else "Друже"
    await message.answer(
        f"{first_name}, привіт, раді бачити ❤️\n\n"
        "Обирай актуальний тур у меню нижче та бронюй місце онлайн без черг!",
        reply_markup=get_main_menu_kb(is_admin=is_admin_user(user_id)),
    )


# ==================== АДМІН-ПАНЕЛЬ ТА КОМАНДИ ====================


@router.message(Command("admin"), StateFilter("*"))
@router.message(F.text == "⚙️ Адмін-панель", StateFilter("*"))
async def show_admin_panel(
    message: Message, state: FSMContext, tour_service: TourService
):
    user_id = message.from_user.id if message.from_user else None
    if not is_admin_user(user_id):
        await message.answer("⛔ Доступ лише для адміністратора.")
        return

    await state.clear()
    tours = await tour_service.list_available_tours()
    text = (
        "⚙️ <b>Адмін-панель STC TRIPS</b>\n\n"
        "Оберіть тур зі списку нижче, щоб переглянути список оплачених учасників "
        "або розіслати групі посилання на організаційний чат:"
    )
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=get_admin_panel_kb(tours),
    )


@router.callback_query(F.data == "admin:main")
async def admin_main_callback(callback: CallbackQuery, tour_service: TourService):
    if not is_admin_user(callback.from_user.id):
        await callback.answer("⛔ Доступ заборонено", show_alert=True)
        return

    tours = await tour_service.list_available_tours()
    text = (
        "⚙️ <b>Адмін-панель STC TRIPS</b>\n\n"
        "Оберіть тур зі списку нижче, щоб переглянути список оплачених учасників "
        "або розіслати групі посилання на організаційний чат:"
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_admin_panel_kb(tours),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:sync")
async def admin_sync_callback(callback: CallbackQuery, tour_service: TourService):
    if not is_admin_user(callback.from_user.id):
        await callback.answer("⛔ Доступ заборонено", show_alert=True)
        return

    await callback.answer("🔄 Синхронізую з Google Таблицею...")
    await callback.message.edit_text("🔄 Синхронізую розклад із Google Таблицею...")
    try:
        from src.inf.sheets.google_sheets import GoogleSheetsService

        sheets = GoogleSheetsService(
            settings.google_credentials_path, settings.google_sheet_id
        )
        count = await tour_service.sync_from_sheets(sheets)
        tours = await tour_service.list_available_tours()
        await callback.message.edit_text(
            f"✅ <b>Успішно синхронізовано!</b> Актуальних турів у базі: <b>{count}</b>\n\n"
            "Оберіть тур для управління:",
            parse_mode="HTML",
            reply_markup=get_admin_panel_kb(tours),
        )
    except Exception as e:
        logger.exception("Помилка синхронізації турів із Google Таблицею")
        tours = await tour_service.list_available_tours()
        await callback.message.edit_text(
            f"❌ Помилка синхронізації: {html.escape(str(e))}",
            parse_mode="HTML",
            reply_markup=get_admin_panel_kb(tours),
        )


@router.callback_query(F.data.startswith("admin:tour:"))
async def admin_tour_details(
    callback: CallbackQuery,
    tour_service: TourService,
    booking_service: BookingService,
):
    if not is_admin_user(callback.from_user.id):
        await callback.answer("⛔ Доступ заборонено", show_alert=True)
        return

    tour_id = int(callback.data.split(":")[2])
    tour = await tour_service.get_tour(tour_id)
    if not tour:
        await callback.answer("Тур не знайдено", show_alert=True)
        return

    confirmed_bookings = await booking_service.get_group_list(tour_id)
    paid_seats = sum(b.tickets_count for b in confirmed_bookings)
    real_left = await tour_service.get_remaining_seats(tour_id)

    text = (
        f"🏔 <b>Тур #{tour.id}: {html.escape(tour.title)}</b>\n"
        f"🗓 Дати: {html.escape(tour.dates)}\n"
        f"💰 Ціна: {tour.price} грн\n"
        f"👥 Оплачено місць: <b>{paid_seats}</b> із {tour.max_seats} (вільно з урахуванням резерву: {real_left})\n"
        f"🧾 Кількість оплачених замовлень: {len(confirmed_bookings)}\n"
        f"💬 Посилання на чат: {html.escape(tour.chat_link)}"
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=get_admin_tour_kb(tour.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:group:"))
async def admin_tour_group_list(
    callback: CallbackQuery,
    tour_service: TourService,
    booking_service: BookingService,
):
    if not is_admin_user(callback.from_user.id):
        await callback.answer("⛔ Доступ заборонено", show_alert=True)
        return

    tour_id = int(callback.data.split(":")[2])
    tour = await tour_service.get_tour(tour_id)
    if not tour:
        await callback.answer("Тур не знайдено", show_alert=True)
        return

    bookings = await booking_service.get_group_list(tour_id)
    if not bookings:
        await callback.answer(
            "На цей тур поки немає оплачених учасників.", show_alert=True
        )
        return

    lines = [
        f"📋 <b>Список групи: {html.escape(tour.title)} ({html.escape(tour.dates)})</b>\n"
    ]
    total_seats = 0
    for idx, b in enumerate(bookings, start=1):
        total_seats += b.tickets_count
        others_str = (
            f"\n   └ Інші: {html.escape(b.other_participants)}"
            if b.tickets_count > 1
            else ""
        )
        lines.append(
            f"{idx}. <b>{html.escape(b.full_name)}</b> ({b.age} р.) — {html.escape(b.phone)} "
            f"[{b.tickets_count} місц., {b.amount} грн]{others_str}"
        )

    lines.append(f"\n<b>Всього оплачено місць: {total_seats} із {tour.max_seats}</b>")
    await callback.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=get_admin_tour_kb(tour.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:send_chat_confirm:"))
async def admin_send_chat_confirm(
    callback: CallbackQuery,
    tour_service: TourService,
    booking_service: BookingService,
):
    if not is_admin_user(callback.from_user.id):
        await callback.answer("⛔ Доступ заборонено", show_alert=True)
        return

    tour_id = int(callback.data.split(":")[2])
    tour = await tour_service.get_tour(tour_id)
    if not tour:
        await callback.answer("Тур не знайдено", show_alert=True)
        return

    bookings = await booking_service.get_group_list(tour_id)
    unique_users = {b.user_telegram_id for b in bookings}
    if not unique_users:
        await callback.answer(
            "На цей тур ще немає оплачених учасників для розсилки!", show_alert=True
        )
        return

    text = (
        f"⚠️ <b>Підтвердження розсилки чату</b>\n\n"
        f"🏔 Тур: <b>{html.escape(tour.title)}</b> ({html.escape(tour.dates)})\n"
        f"🔗 Посилання: {html.escape(tour.chat_link)}\n"
        f"👥 Отримувачів (унікальних Telegram-акаунтів): <b>{len(unique_users)}</b>\n\n"
        f"Ви впевнені, що хочете надіслати посилання на чат усім учасникам зараз?"
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=get_admin_confirm_chat_kb(tour_id),
    )
    await callback.answer()


async def _execute_chat_broadcast(
    bot: Bot, tour_id: int, tour_service: TourService, booking_service: BookingService
) -> str:
    tour = await tour_service.get_tour(tour_id)
    if not tour:
        return f"❌ Тур із ID {tour_id} не знайдено."

    bookings = await booking_service.get_group_list(tour_id)
    unique_user_ids = {b.user_telegram_id for b in bookings}

    if not unique_user_ids:
        return f"ℹ️ На тур «{html.escape(tour.title)}» поки немає підтверджених учасників."

    sent_count = 0
    failed_count = 0
    safe_title = html.escape(tour.title)
    safe_link = html.escape(tour.chat_link)

    for user_id in unique_user_ids:
        try:
            await bot.send_message(
                chat_id=user_id,
                text=(
                    f"🚌 Вже скоро вирушаємо у тур <b>{safe_title}</b>!\n"
                    f"Приєднуйтесь до організаційного чату нашої групи: {safe_link}"
                ),
                parse_mode="HTML",
            )
            sent_count += 1
        except Exception:
            failed_count += 1
            logger.warning(
                "Не вдалося надіслати посилання на чат користувачу %s", user_id
            )
        await asyncio.sleep(0.05)

    status_text = f"✅ Посилання на чат туру «<b>{safe_title}</b>» успішно розіслано (<b>{sent_count}</b> учасникам)."
    if failed_count > 0:
        status_text += f"\n⚠️ Не вдалося доставити: {failed_count} (бот заблокований користувачем)."
    return status_text


@router.callback_query(F.data.startswith("admin:send_chat_run:"))
async def admin_send_chat_run(
    callback: CallbackQuery,
    bot: Bot,
    tour_service: TourService,
    booking_service: BookingService,
):
    if not is_admin_user(callback.from_user.id):
        await callback.answer("⛔ Доступ заборонено", show_alert=True)
        return

    tour_id = int(callback.data.split(":")[2])
    await callback.answer("📨 Розпочинаю розсилку...")
    await callback.message.edit_text("⏳ Триває розсилка посилання учасникам...")

    result_html = await _execute_chat_broadcast(
        bot, tour_id, tour_service, booking_service
    )
    await callback.message.edit_text(
        result_html,
        parse_mode="HTML",
        reply_markup=get_admin_tour_kb(tour_id),
    )


@router.message(Command("sync_tours"), StateFilter("*"))
async def cmd_sync_tours(message: Message, tour_service: TourService):
    user_id = message.from_user.id if message.from_user else None
    if not is_admin_user(user_id):
        await message.answer(
            f"⛔ Доступ заборонено.\n"
            f"Твій ID: <code>{user_id}</code>\n"
            f"В .env прописано: <code>{settings.admin_chat_id}</code>",
            parse_mode="HTML",
        )
        return

    wait_msg = await message.answer("🔄 Синхронізую розклад із Google Таблицею...")
    try:
        from src.inf.sheets.google_sheets import GoogleSheetsService

        sheets = GoogleSheetsService(
            settings.google_credentials_path, settings.google_sheet_id
        )
        count = await tour_service.sync_from_sheets(sheets)
        await wait_msg.edit_text(
            f"✅ Успішно синхронізовано! Актуальних турів у базі: <b>{count}</b>",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.exception("Помилка синхронізації турів із Google Таблицею")
        await wait_msg.edit_text(f"❌ Помилка синхронізації: {e}")


@router.message(Command("send_chat_link"))
async def broadcast_chat_link(
    message: Message,
    bot: Bot,
    tour_service: TourService,
    booking_service: BookingService,
):
    """Команда адміна (/send_chat_link або /send_chat_link <id_туру>)."""
    user_id = message.from_user.id if message.from_user else None
    if not is_admin_user(user_id):
        return

    parts = (message.text or "").split()
    if len(parts) < 2 or not parts[1].isdigit():
        # Якщо адмін не вказав ID — відкриваємо інтерактивний вибір туру кнопками!
        tours = await tour_service.list_available_tours()
        await message.answer(
            "Оберіть тур, для якого потрібно надіслати посилання на чат:",
            reply_markup=get_admin_panel_kb(tours),
        )
        return

    tour_id = int(parts[1])
    result_html = await _execute_chat_broadcast(
        bot, tour_id, tour_service, booking_service
    )
    await message.answer(result_html, parse_mode="HTML")


# ==================== КЛІЄНТСЬКІ ХЕНДЛЕРИ ====================


@router.message(F.text == "❌ Скасувати", StateFilter("*"))
async def cancel_booking(message: Message, state: FSMContext):
    current_state = await state.get_state()
    user_id = message.from_user.id if message.from_user else None
    await state.clear()

    if current_state is None:
        await message.answer(
            "Ви у головному меню.",
            reply_markup=get_main_menu_kb(is_admin=is_admin_user(user_id)),
        )
        return

    await message.answer(
        "🛑 Бронювання скасовано. Ви повернулися до головного меню.",
        reply_markup=get_main_menu_kb(is_admin=is_admin_user(user_id)),
    )


@router.message(F.text == "🏔 Обрати тур")
async def show_tours(message: Message, tour_service: TourService):
    tours = await tour_service.list_available_tours()
    if not tours:
        await message.answer("Наразі актуальних турів немає. Слідкуйте за оновленнями!")
        return
    await message.answer("Оберіть тур зі списку:", reply_markup=get_tours_kb(tours))


@router.message(F.text == "❓ Поширені питання та Умови")
async def show_faq(message: Message):
    await message.answer(
        FAQ_MAIN_TEXT,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=get_faq_menu_kb(FAQ_DATA),
    )


@router.callback_query(F.data.startswith("faq:"))
async def faq_navigation(callback: CallbackQuery):
    key = callback.data.split(":")[1]

    if key == "main":
        await callback.message.edit_text(
            FAQ_MAIN_TEXT,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=get_faq_menu_kb(FAQ_DATA),
        )
    elif key in FAQ_DATA:
        _, answer_text = FAQ_DATA[key]
        await callback.message.edit_text(
            answer_text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=get_faq_back_kb(),
        )

    await callback.answer()


@router.message(F.text == "💬 Зв'язок з менеджером")
async def contact_manager(message: Message):
    await message.answer(
        f"Маєте додаткові запитання? Напишіть нашому менеджеру: @{settings.manager_username}"
    )


@router.callback_query(F.data.startswith("tour:"))
async def tour_details(callback: CallbackQuery, tour_service: TourService):
    tour_id = int(callback.data.split(":")[1])
    tour = await tour_service.get_tour(tour_id)
    if not tour or not tour.is_active:
        await callback.answer("Тур не знайдено або вже не актуальний", show_alert=True)
        return

    real_left = await tour_service.get_remaining_seats(tour_id)
    seats_info = tour_service.format_marketing_seats_text(real_left)

    text = (
        f"<b>{html.escape(tour.title)}</b>\n"
        f"🗺 програма: {html.escape(tour.program_url)}\n\n"
        f"🗓 {html.escape(tour.dates)}\n"
        f"💳 Вартість: {tour.price} грн/особи\n"
        f"{html.escape(seats_info)}\n\n"
        f"<b>У неї входить:</b>\n{html.escape(tour.included_details)}"
    )
    await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=get_tour_action_kb(tour.id, tour.program_url),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("book:"))
async def start_booking(
    callback: CallbackQuery, state: FSMContext, tour_service: TourService
):
    tour_id = int(callback.data.split(":")[1])
    real_left = await tour_service.get_remaining_seats(tour_id)

    if real_left <= 0:
        await callback.answer(
            "😔 На жаль, усі місця на цей тур вже розкуплено!", show_alert=True
        )
        return

    await state.update_data(tour_id=tour_id)
    await state.set_state(BookingForm.waiting_for_full_name)

    await callback.message.answer(
        "Введіть Ваше ПІБ (Прізвище, Ім'я, По батькові):",
        reply_markup=get_cancel_kb(),
    )
    await callback.answer()


@router.message(BookingForm.waiting_for_full_name, F.text)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()

    if len(name.split()) < 2 or not re.match(r"^[А-Яа-яІіЇїЄєҐґA-Za-z\s\-’']+$", name):
        await message.answer(
            "⚠️ Будь ласка, введіть повне ПІБ (мінімум два слова, лише літери).\nСпробуйте ще раз:"
        )
        return

    await state.update_data(full_name=name)
    await state.set_state(BookingForm.waiting_for_phone)
    await message.answer(
        "Введіть Ваш контактний номер телефону (у будь-якому форматі: 097..., 098..., 067..., 050..., +380...) "
        "або натисніть кнопку <b>«📱 Надіслати мій номер»</b> нижче:",
        parse_mode="HTML",
        reply_markup=get_phone_kb(),
    )


@router.message(BookingForm.waiting_for_phone, F.text | F.contact)
async def process_phone(message: Message, state: FSMContext):
    phone_raw = (
        message.contact.phone_number
        if message.contact
        else (message.text or "").strip()
    )
    normalized_phone = normalize_phone_number(phone_raw)

    if not normalized_phone:
        await message.answer(
            "⚠️ Некоректний номер телефону.\n"
            "Будь ласка, введіть дійсний номер (наприклад: <code>0981234567</code>, <code>097 123 45 67</code>, "
            "<code>0671234567</code> або <code>+380501234567</code>) чи натисніть кнопку «📱 Надіслати мій номер»:",
            parse_mode="HTML",
        )
        return

    await state.update_data(phone=normalized_phone)
    await state.set_state(BookingForm.waiting_for_age)
    await message.answer(
        "Вкажіть Ваш вік (лише числом):",
        reply_markup=get_cancel_kb(),
    )


@router.message(BookingForm.waiting_for_age, F.text)
async def process_age(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit() or not (14 <= int(text) <= 100):
        await message.answer("⚠️ Вкажіть реальний вік цифрою (наприклад: 24):")
        return

    await state.update_data(age=int(text))
    await state.set_state(BookingForm.waiting_for_tickets_count)
    await message.answer(
        "🎟 <b>Скільки всього місць ви хочете забронювати?</b>\n"
        "(Введіть цифру, наприклад: 1 — якщо їдете самі, 2 — якщо вдвох і т.д.)",
        parse_mode="HTML",
    )


@router.message(BookingForm.waiting_for_tickets_count, F.text)
async def process_tickets_count(
    message: Message, state: FSMContext, tour_service: TourService
):
    text = message.text.strip()
    if not text.isdigit() or not (1 <= int(text) <= 20):
        await message.answer("⚠️ Вкажіть цифру від 1 до 20:")
        return

    tickets_count = int(text)
    data = await state.get_data()
    real_left = await tour_service.get_remaining_seats(data["tour_id"])

    if tickets_count > real_left:
        await message.answer(
            f"⚠️ На жаль, у цьому турі залишилось лише <b>{real_left}</b> вільних місць.\n"
            f"Будь ласка, введіть меншу кількість або натисніть «❌ Скасувати»:",
            parse_mode="HTML",
        )
        return

    await state.update_data(tickets_count=tickets_count)

    if tickets_count == 1:
        await state.update_data(other_participants="немає")
        await state.set_state(BookingForm.waiting_for_terms_agreement)
        await message.answer(
            "Перед переходом до оплати, будь ласка, ознайомтеся та погодьтеся з умовами бронювання:",
            reply_markup=get_terms_agreement_kb(),
        )
    else:
        await state.set_state(BookingForm.waiting_for_other_participants)
        await message.answer(
            f"👥 Ви бронюєте {tickets_count} місць.\n\n"
            f"Будь ласка, вкажіть ПІБ та вік для <b>інших {tickets_count - 1} учасників</b> єдиним повідомленням:",
            parse_mode="HTML",
        )


@router.message(BookingForm.waiting_for_other_participants, F.text)
async def process_others(message: Message, state: FSMContext):
    text = message.text.strip()
    if len(text) < 5:
        await message.answer("⚠️ Напишіть детальніше (ПІБ та вік інших учасників):")
        return

    await state.update_data(other_participants=text)
    await state.set_state(BookingForm.waiting_for_terms_agreement)
    await message.answer(
        "Перед переходом до оплати, будь ласка, ознайомтеся та погодьтеся з умовами бронювання:",
        reply_markup=get_terms_agreement_kb(),
    )


@router.message(
    StateFilter(
        BookingForm.waiting_for_full_name,
        BookingForm.waiting_for_phone,
        BookingForm.waiting_for_age,
        BookingForm.waiting_for_tickets_count,
        BookingForm.waiting_for_other_participants,
    )
)
async def process_unexpected_non_text(message: Message):
    await message.answer(
        "⚠️ Будь ласка, надішліть відповідь текстовим повідомленням або натисніть «❌ Скасувати»."
    )


@router.callback_query(BookingForm.waiting_for_terms_agreement, F.data == "agree_terms")
async def process_terms_and_send_payment_link(
    callback: CallbackQuery,
    state: FSMContext,
    booking_service: BookingService,
):
    data = await state.get_data()
    await state.clear()
    user_id = callback.from_user.id

    try:
        booking, tour, payment_url = (
            await booking_service.create_booking_with_payment_link(
                user_telegram_id=user_id,
                tour_id=data["tour_id"],
                full_name=data["full_name"],
                phone=data["phone"],
                age=data["age"],
                tickets_count=data["tickets_count"],
                other_participants=data["other_participants"],
            )
        )
    except ValueError as e:
        await callback.message.answer(
            f"❌ Помилка бронювання: {e}",
            reply_markup=get_main_menu_kb(is_admin=is_admin_user(user_id)),
        )
        await callback.answer()
        return

    first_name = html.escape(callback.from_user.first_name or "Друже")
    details_msg = (
        f"{first_name}, привіт, раді бачити ❤️\n\n"
        f"Бронювання туру: <b>{html.escape(tour.title)}</b>\n"
        f"👥 Кількість місць: {booking.tickets_count}\n"
        f"💳 <b>Вартість до сплати: {booking.amount} грн</b>\n\n"
        f"⏳ Дедлайн оплати: {html.escape(tour.payment_deadline)}\n"
    )

    await callback.message.answer(
        "✅ Анкету успішно сформовано!",
        reply_markup=get_main_menu_kb(is_admin=is_admin_user(user_id)),
    )

    await callback.message.answer(
        details_msg,
        parse_mode="HTML",
        reply_markup=get_payment_kb(payment_url),
    )
    await callback.answer()
