import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import html
import logging
import re

try:
    KYIV_TZ = ZoneInfo("Europe/Kyiv")
except ZoneInfoNotFoundError:
    KYIV_TZ = datetime.now().astimezone().tzinfo or timezone(timedelta(hours=2))
from pathlib import Path
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext

from src.config import settings
from src.app.services import TourService, BookingService
from src.pres.bot.states import (
    BookingForm,
    LoyalRequestForm,
    ManagerCustomPriceForm,
)
from src.pres.bot.keyboards import (
    get_main_menu_kb,
    get_managers_group_kb,
    get_tours_kb,
    get_tour_action_kb,
    get_terms_agreement_kb,
    get_cancel_kb,
    get_skip_or_cancel_kb,
    get_phone_kb,
    get_ubd_children_kb,
    get_faq_menu_kb,
    get_faq_back_kb,
    get_loyal_request_start_kb,
    get_loyal_manager_decision_kb,
    get_large_group_manager_kb,
    get_large_group_confirm_step_kb,
    get_large_group_cancel_step_kb,
    get_receipt_manager_kb,
    get_receipt_confirm_step_kb,
    get_receipt_reject_step_kb,
    get_admin_panel_kb,
    get_admin_tour_kb,
    get_admin_confirm_chat_kb,
)

logger = logging.getLogger(__name__)
router = Router()

UA_OPERATOR_CODES = {
    "39", "50", "63", "66", "67", "68", "73", "75", "77",
    "89", "91", "92", "93", "94", "95", "96", "97", "98", "99",
}


def normalize_phone_number(raw_phone: str) -> str | None:
    cleaned = re.sub(r"[\s\-\(\)\.]", "", raw_phone.strip())
    has_plus = cleaned.startswith("+")
    digits = re.sub(r"\D", "", cleaned)

    if len(digits) == 12 and digits.startswith("380"):
        if digits[3:5] in UA_OPERATOR_CODES:
            return f"+{digits}"
    elif len(digits) == 11 and digits.startswith("80"):
        if digits[2:4] in UA_OPERATOR_CODES:
            return f"+3{digits}"
    elif len(digits) == 10 and digits.startswith("0"):
        if digits[1:3] in UA_OPERATOR_CODES:
            return f"+38{digits}"
    elif len(digits) == 9 and not has_plus:
        if digits[0:2] in UA_OPERATOR_CODES:
            return f"+380{digits}"

    if has_plus and 10 <= len(digits) <= 15 and not digits.startswith("380"):
        return f"+{digits}"

    return None


def is_managers_chat(chat_id: int | None) -> bool:
    """Перевіряє, чи дія відбувається у робочій групі менеджерів (ADMIN_CHAT_ID)."""
    return chat_id is not None and chat_id == settings.admin_chat_id


def format_manager_name(user) -> str:
    if not user:
        return "Менеджер"
    if user.username:
        return f"@{html.escape(user.username)}"
    return html.escape(user.full_name or "Менеджер")


FAQ_MAIN_TEXT = (
    "📌 <b>Корисна інформація та Поширені питання (FAQ)</b>\n\n"
    f"📃 Договір публічної оферти: {settings.public_offer_url}\n"
    f"📃 Опис умов повернення коштів: {settings.refund_policy_url}\n\n"
    "👇 <b>Оберіть питання зі списку нижче, щоб переглянути відповідь:</b>"
)

IBAN_NUMBER = "UA583052990000026004001016360"
IBAN_PURPOSE = "За послуги по договору публічної оферти"
IBAN_HOWTO_URL = "https://cutt.ly/lR34hxj"


def build_iban_requisites_text() -> str:
    return (
        "✅ <b>Реквізити на оплату послуг компанії:</b>\n\n"
        "▫️ Найменування отримувача: <b>ФОП Озарко Тарас-Ярослав Петрович</b>\n"
        "▫️ Код отримувача: <code>3659407214</code>\n"
        f"👉🏻 Рахунок отримувача у форматі відповідно до стандарту IBAN:\n<code>{IBAN_NUMBER}</code>\n"
        '▫️ Назва банку: <b>АТ КБ "ПРИВАТБАНК"</b>\n'
        f"👉🏻 Призначення платежу в платіжці: «<code>{IBAN_PURPOSE}</code>»\n\n"
        "УВАГА❗️ Платежі з неправильно вказаним призначенням або без нього: повертаються, як не з'ясовані!\n\n"
        "▫️ <b>Прохання опісля оплати надіслати скрін-квитанцію сюди у бот!</b>\n\n"
        f"🙋🏻‍♂️ Як здійснити оплату на рахунок IBAN? {IBAN_HOWTO_URL}\n"
        f"📃 Договір публічної оферти: {settings.public_offer_url}\n"
        f"📃 Опис умов повернення коштів: {settings.refund_policy_url}"
    )


async def send_iban_payment_instructions(
    bot: Bot, chat_id: int, summary_html: str
) -> None:
    await bot.send_message(
        chat_id=chat_id,
        text=f"{summary_html}\n{build_iban_requisites_text()}",
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await bot.send_message(
        chat_id=chat_id,
        text=IBAN_NUMBER,
    )
    await bot.send_message(
        chat_id=chat_id,
        text=f"«{IBAN_PURPOSE}»",
    )
    await bot.send_message(
        chat_id=chat_id,
        text=(
            "📸 <b>Очікуємо на скрін-квитанцію!</b>\n"
            "Будь ласка, надішліть у цей чат <b>фото (скріншот) або PDF-файл квитанції</b> про оплату — "
            "менеджер перевірить платіж і підтвердить ваше бронювання ❤️"
        ),
        parse_mode="HTML",
        reply_markup=get_cancel_kb(),
    )


# ==================== ДОПОМІЖНА КОМАНДА /id ====================


@router.message(Command("id"), StateFilter("*"))
async def cmd_get_id(message: Message):
    user_id = message.from_user.id if message.from_user else "unknown"
    await message.answer(
        f"🆔 <b>ID цього чату (для ADMIN_CHAT_ID в .env):</b> <code>{message.chat.id}</code>\n"
        f"👤 <b>Ваш особистий ID:</b> <code>{user_id}</code>",
        parse_mode="HTML",
    )


# ==================== РОБОЧА ГРУПА МЕНЕДЖЕРІВ (АДМІН-ФУНКЦІОНАЛ) ====================


@router.message(Command("admin"), StateFilter("*"))
@router.message(F.text == "⚙️ Панель управління", StateFilter("*"))
async def show_admin_panel(
    message: Message, state: FSMContext, tour_service: TourService
):
    if not is_managers_chat(message.chat.id):
        await message.answer(
            "⛔ Команда /admin працює лише у робочій групі менеджерів.\n"
            f"(ID цього чату: <code>{message.chat.id}</code>)",
            parse_mode="HTML",
        )
        return

    await state.clear()
    tours = await tour_service.list_available_tours()
    text = (
        "⚙️ <b>Панель управління STC TRIPS (Група менеджерів)</b>\n\n"
        "• Команда <code>/add_promo КОД СУМА</code> — додати промокод у базу й таблицю (напр. <code>/add_promo SUMMER 100</code>)\n"
        "• Команда <code>/del_promo КОД</code> — видалити промокод із бази й таблиці (напр. <code>/del_promo SUMMER</code>)\n"
        "• Оберіть тур нижче для перегляду списку учасників або розсилки чату:"
    )
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=get_managers_group_kb(),
    )
    await message.answer(
        "👇 <b>Активні тури та дії:</b>",
        parse_mode="HTML",
        reply_markup=get_admin_panel_kb(tours),
    )


@router.message(Command("add_promo"), StateFilter("*"))
async def cmd_add_promo(message: Message, booking_service: BookingService):
    if not is_managers_chat(message.chat.id):
        return

    parts = (message.text or "").split()
    if len(parts) < 3 or not parts[2].isdigit() or int(parts[2]) <= 0:
        await message.answer(
            "Використання: <code>/add_promo КОД СУМА_З_ОСОБИ</code>\n"
            "Приклад: <code>/add_promo SUMMER 100</code>",
            parse_mode="HTML",
        )
        return

    code = parts[1].strip().upper()
    discount = int(parts[2])
    await booking_service.upsert_promo_code(code, discount)
    await message.answer(
        f"✅ Промокод <code>{html.escape(code)}</code> на знижку <b>-{discount} грн/ос</b> збережено і в базу, і у вкладку «Промокоди» Google Таблиці!",
        parse_mode="HTML",
    )


@router.message(Command("del_promo"), StateFilter("*"))
async def cmd_del_promo(message: Message, booking_service: BookingService):
    if not is_managers_chat(message.chat.id):
        return

    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer(
            "Використання: <code>/del_promo КОД</code>\n"
            "Приклад: <code>/del_promo SUMMER</code>",
            parse_mode="HTML",
        )
        return

    code = parts[1].strip().upper()
    deleted = await booking_service.delete_promo_code(code)
    if deleted:
        await message.answer(
            f"🗑 Промокод <code>{html.escape(code)}</code> вимкнено та видалено з Google Таблиці!",
            parse_mode="HTML",
        )
    else:
        await message.answer(
            f"ℹ️ Промокод <code>{html.escape(code)}</code> не знайдено.",
            parse_mode="HTML",
        )


@router.callback_query(F.data == "admin:main")
async def admin_main_callback(callback: CallbackQuery, tour_service: TourService):
    if not is_managers_chat(callback.message.chat.id):
        await callback.answer("⛔ Доступ лише в групі менеджерів", show_alert=True)
        return

    tours = await tour_service.list_available_tours()
    text = (
        "⚙️ <b>Панель управління STC TRIPS (Група менеджерів)</b>\n\n"
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
    if not is_managers_chat(callback.message.chat.id):
        await callback.answer("⛔ Доступ лише в групі менеджерів", show_alert=True)
        return

    await callback.answer("🔄 Синхронізую з Google Таблицею...")
    await callback.message.edit_text(
        "🔄 Синхронізую Розклад, FAQ та Промокоди з Google Таблицею..."
    )
    try:
        from src.inf.sheets.google_sheets import GoogleSheetsService

        sheets = GoogleSheetsService(
            settings.google_credentials_path, settings.google_sheet_id
        )
        tours_cnt, faqs_cnt, promos_cnt = await tour_service.sync_from_sheets(sheets)
        tours = await tour_service.list_available_tours()
        await callback.message.edit_text(
            f"✅ <b>Успішно синхронізовано з Google Таблицею!</b>\n"
            f"🏔 Актуальних турів: <b>{tours_cnt}</b>\n"
            f"❓ Питань у FAQ: <b>{faqs_cnt}</b>\n"
            f"🎟 Активних промокодів: <b>{promos_cnt}</b>\n\n"
            "Оберіть тур для управління:",
            parse_mode="HTML",
            reply_markup=get_admin_panel_kb(tours),
        )
    except Exception as e:
        logger.exception("Помилка синхронізації з Google Таблицею")
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
    if not is_managers_chat(callback.message.chat.id):
        await callback.answer("⛔ Доступ лише в групі менеджерів", show_alert=True)
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
        f"🗓 Дати: {html.escape(tour.dates)} ({tour.duration_days} дн.)\n"
        f"💰 Базова ціна: {tour.price} грн\n"
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
    if not is_managers_chat(callback.message.chat.id):
        await callback.answer("⛔ Доступ лише в групі менеджерів", show_alert=True)
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
        user_tag = f" (@{html.escape(b.username)})" if b.username else ""
        others_str = (
            f"\n   👥 Інші: {html.escape(b.other_participants)}"
            if b.tickets_count > 1
            else ""
        )
        disc_str = (
            f"\n   🏷 Знижка/Пільга: <b>{html.escape(b.discount_info)}</b>"
            if b.discount_info and b.discount_info != "немає"
            else ""
        )
        note_str = (
            f"\n   📝 Нотатка: <i>{html.escape(b.notes)}</i>"
            if b.notes and b.notes != "немає"
            else ""
        )
        lines.append(
            f"{idx}. <b>{html.escape(b.full_name)}</b>{user_tag} ({b.age} р.) — {html.escape(b.phone)} "
            f"[{b.tickets_count} місц., {b.amount} грн]{others_str}{disc_str}{note_str}"
        )

    lines.append(f"\n<b>Всього оплачено місць: {total_seats} із {tour.max_seats}</b>")
    full_text = "\n".join(lines)

    # Захист від перевищення ліміту Telegram (4096 символів) при великій групі
    if len(full_text) <= 3800:
        await callback.message.edit_text(
            full_text,
            parse_mode="HTML",
            reply_markup=get_admin_tour_kb(tour.id),
        )
    else:
        chunks: list[str] = []
        current_chunk: list[str] = []
        current_len = 0
        for line in lines:
            if current_len + len(line) + 1 > 3800 and current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = [line]
                current_len = len(line)
            else:
                current_chunk.append(line)
                current_len += len(line) + 1
        if current_chunk:
            chunks.append("\n".join(current_chunk))

        await callback.message.edit_text(chunks[0], parse_mode="HTML")
        for chunk in chunks[1:-1]:
            await callback.message.answer(chunk, parse_mode="HTML")
        await callback.message.answer(
            chunks[-1],
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
    if not is_managers_chat(callback.message.chat.id):
        await callback.answer("⛔ Доступ лише в групі менеджерів", show_alert=True)
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
    if not is_managers_chat(callback.message.chat.id):
        await callback.answer("⛔ Доступ лише в групі менеджерів", show_alert=True)
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
@router.message(F.text == "🔄 Синхронізувати таблицю", StateFilter("*"))
async def cmd_sync_tours(message: Message, tour_service: TourService):
    if not is_managers_chat(message.chat.id):
        await message.answer(
            f"⛔ Ця команда працює лише в робочій групі менеджерів.\n"
            f"ID цього чату: <code>{message.chat.id}</code>",
            parse_mode="HTML",
        )
        return

    wait_msg = await message.answer(
        "🔄 Синхронізую Розклад, FAQ та Промокоди з Google Таблицею..."
    )
    try:
        from src.inf.sheets.google_sheets import GoogleSheetsService

        sheets = GoogleSheetsService(
            settings.google_credentials_path, settings.google_sheet_id
        )
        tours_cnt, faqs_cnt, promos_cnt = await tour_service.sync_from_sheets(sheets)
        await wait_msg.edit_text(
            f"✅ <b>Успішно синхронізовано!</b>\n"
            f"🏔 Актуальних турів: <b>{tours_cnt}</b>\n"
            f"❓ Питань FAQ: <b>{faqs_cnt}</b>\n"
            f"🎟 Промокодів: <b>{promos_cnt}</b>",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.exception("Помилка синхронізації з Google Таблицею")
        await wait_msg.edit_text(f"❌ Помилка синхронізації: {e}")


@router.message(Command("send_chat_link"))
async def broadcast_chat_link(
    message: Message,
    bot: Bot,
    tour_service: TourService,
    booking_service: BookingService,
):
    if not is_managers_chat(message.chat.id):
        return

    parts = (message.text or "").split()
    if len(parts) < 2 or not parts[1].isdigit():
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


# ==================== ОБРОБКА ЗАПИТІВ МЕНЕДЖЕРАМИ У ГРУПІ ====================


@router.callback_query(F.data.startswith("loyal:approve:"))
async def manager_approve_loyal(
    callback: CallbackQuery, bot: Bot, booking_service: BookingService
):
    if not is_managers_chat(callback.message.chat.id):
        await callback.answer("⛔ Доступ лише в групі менеджерів", show_alert=True)
        return

    target_user_id = int(callback.data.split(":")[2])
    await booking_service.set_loyal_status(
        telegram_id=target_user_id, is_loyal=True, pending=False
    )
    mgr = format_manager_name(callback.from_user)

    await callback.message.edit_text(
        f"{callback.message.html_text}\n\n"
        f"✅ <b>Статус постійного клієнта ПІДТВЕРДЖЕНО</b> (опрацював: {mgr})",
        parse_mode="HTML",
    )
    try:
        await bot.send_message(
            chat_id=target_user_id,
            text=(
                "🎉 <b>Вітаємо! Ваш статус постійного клієнта STC TRIPS підтверджено!</b>\n\n"
                "Тепер під час бронювання турів у боті для вас автоматично діятиме знижка постійного клієнта ❤️"
            ),
            parse_mode="HTML",
        )
    except Exception:
        logger.warning("Не вдалося повідомити клієнта %s про статус", target_user_id)
    await callback.answer("✅ Статус підтверджено!")


@router.callback_query(F.data.startswith("loyal:reject:"))
async def manager_reject_loyal(
    callback: CallbackQuery, bot: Bot, booking_service: BookingService
):
    if not is_managers_chat(callback.message.chat.id):
        await callback.answer("⛔ Доступ лише в групі менеджерів", show_alert=True)
        return

    target_user_id = int(callback.data.split(":")[2])
    await booking_service.set_loyal_status(
        telegram_id=target_user_id, is_loyal=False, pending=False
    )
    mgr = format_manager_name(callback.from_user)

    await callback.message.edit_text(
        f"{callback.message.html_text}\n\n"
        f"❌ <b>Запит на статус постійного клієнта ВІДХИЛЕНО</b> (опрацював: {mgr})",
        parse_mode="HTML",
    )
    try:
        await bot.send_message(
            chat_id=target_user_id,
            text=(
                "ℹ️ На жаль, менеджер не зміг знайти достатню кількість ваших попередніх поїздок для "
                "статусу постійного клієнта (потрібно 2+ тури).\n"
                f"Якщо виникла помилка — напишіть менеджеру: @{settings.manager_username}"
            ),
        )
    except Exception:
        logger.warning("Не вдалося повідомити клієнта %s про відхилення", target_user_id)
    await callback.answer("Запит відхилено")


@router.callback_query(F.data.startswith("mgr_group:price:"))
async def manager_ask_custom_price(callback: CallbackQuery, state: FSMContext):
    if not is_managers_chat(callback.message.chat.id):
        await callback.answer("⛔ Доступ лише в групі менеджерів", show_alert=True)
        return

    booking_id = int(callback.data.split(":")[2])
    await state.update_data(
        custom_price_booking_id=booking_id,
        group_msg_id=callback.message.message_id,
        group_msg_html=callback.message.html_text,
    )
    await state.set_state(ManagerCustomPriceForm.waiting_for_custom_amount)
    await callback.message.reply(
        f"💳 Введіть узгоджену загальну суму до сплати (у грн, лише числом) для <b>Бронювання #{booking_id}</b>.\n"
        "Після введення бот автоматично надішле клієнту реквізити IBAN та попросить надіслати квитанцію:",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(ManagerCustomPriceForm.waiting_for_custom_amount, F.text)
async def manager_set_custom_price(
    message: Message,
    state: FSMContext,
    bot: Bot,
    booking_service: BookingService,
):
    if not is_managers_chat(message.chat.id):
        return

    text = message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await message.reply("⚠️ Введіть суму додатним числом (наприклад: 5800):")
        return

    custom_amount = int(text)
    data = await state.get_data()
    booking_id = data["custom_price_booking_id"]
    group_msg_id = data.get("group_msg_id")
    group_msg_html = data.get("group_msg_html", "")
    await state.clear()

    res = await booking_service.set_custom_price_and_get_payment_url(
        booking_id=booking_id, custom_amount=custom_amount
    )
    if not res:
        await message.reply("❌ Бронювання не знайдено.")
        return

    booking, tour, _ = res
    mgr = format_manager_name(message.from_user)
    deadline_str = (datetime.now(KYIV_TZ) + timedelta(minutes=15)).strftime("%H:%M")

    summary_html = (
        f"🎉 <b>Індивідуальний прорахунок для вашої компанії готовий!</b>\n\n"
        f"🏔 Тур: <b>{html.escape(tour.title)}</b> ({html.escape(tour.dates)})\n"
        f"👥 Кількість місць: <b>{booking.tickets_count}</b>\n"
        f"💳 <b>Узгоджена вартість зі знижкою: {booking.amount} грн</b>\n"
        f"⏳ Бронь місць діє до: <b>{deadline_str}</b> (15 хв на оплату)\n"
    )

    try:
        await send_iban_payment_instructions(
            bot=bot,
            chat_id=booking.user_telegram_id,
            summary_html=summary_html,
        )
    except Exception as e:
        await message.reply(f"⚠️ Не вдалося надіслати реквізити клієнту: {e}")
        return

    if group_msg_id and group_msg_html:
        try:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=group_msg_id,
                text=(
                    f"{group_msg_html}\n\n"
                    f"💳 <b>Виставлено рахунок на {custom_amount} грн</b> (менеджер: {mgr}). Очікуємо квитанцію від клієнта."
                ),
                parse_mode="HTML",
                reply_markup=get_large_group_manager_kb(booking_id),
            )
        except Exception:
            pass

    await message.reply(
        f"✅ Реквізити на оплату <b>{custom_amount} грн</b> успішно надіслано клієнту {html.escape(booking.full_name)}!\n"
        "Коли клієнт надішле квитанцію в бот, вона з'явиться тут у чаті.",
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("mgr_group:confirm_ask:"))
async def manager_ask_confirm_group_booking(callback: CallbackQuery):
    if not is_managers_chat(callback.message.chat.id):
        await callback.answer("⛔ Доступ лише в групі менеджерів", show_alert=True)
        return

    booking_id = int(callback.data.split(":")[2])
    await callback.answer(
        f"⚠️ Ви впевнені, що хочете підтвердити оплату для бронювання #{booking_id}?\n"
        "Натисніть зелену кнопку нижче для остаточного підтвердження.",
        show_alert=True,
    )
    await callback.message.edit_reply_markup(
        reply_markup=get_large_group_confirm_step_kb(booking_id)
    )


@router.callback_query(F.data.startswith("mgr_group:cancel_ask:"))
async def manager_ask_cancel_group_booking(callback: CallbackQuery):
    if not is_managers_chat(callback.message.chat.id):
        await callback.answer("⛔ Доступ лише в групі менеджерів", show_alert=True)
        return

    booking_id = int(callback.data.split(":")[2])
    await callback.answer(
        f"⚠️ Ви впевнені, що хочете скасувати заявку #{booking_id}?",
        show_alert=True,
    )
    await callback.message.edit_reply_markup(
        reply_markup=get_large_group_cancel_step_kb(booking_id)
    )


@router.callback_query(F.data.startswith("mgr_group:back:"))
async def manager_back_group_booking(callback: CallbackQuery):
    if not is_managers_chat(callback.message.chat.id):
        await callback.answer("⛔ Доступ лише в групі менеджерів", show_alert=True)
        return

    booking_id = int(callback.data.split(":")[2])
    await callback.message.edit_reply_markup(
        reply_markup=get_large_group_manager_kb(booking_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("mgr_group:confirm:"))
async def manager_confirm_group_booking(
    callback: CallbackQuery, booking_service: BookingService
):
    if not is_managers_chat(callback.message.chat.id):
        await callback.answer("⛔ Доступ лише в групі менеджерів", show_alert=True)
        return

    booking_id = int(callback.data.split(":")[2])
    mgr = format_manager_name(callback.from_user)
    res = await booking_service.confirm_booking_manually(booking_id, mgr)
    if not res:
        await callback.answer("Бронювання не знайдено", show_alert=True)
        return

    await callback.message.edit_text(
        f"{callback.message.html_text}\n\n"
        f"✅ <b>Заявку закрито — бронювання підтверджено та додано в таблицю!</b> (опрацював: {mgr})",
        parse_mode="HTML",
    )
    await callback.answer("✅ Бронювання підтверджено!")


@router.callback_query(F.data.startswith("mgr_group:cancel:"))
async def manager_cancel_group_booking(
    callback: CallbackQuery, bot: Bot, booking_service: BookingService
):
    if not is_managers_chat(callback.message.chat.id):
        await callback.answer("⛔ Доступ лише в групі менеджерів", show_alert=True)
        return

    booking_id = int(callback.data.split(":")[2])
    mgr = format_manager_name(callback.from_user)
    updated = await booking_service.cancel_booking_by_manager(booking_id)
    if not updated:
        await callback.answer("Бронювання не знайдено", show_alert=True)
        return

    await callback.message.edit_text(
        f"{callback.message.html_text}\n\n"
        f"❌ <b>Заявку скасовано</b> (опрацював: {mgr})",
        parse_mode="HTML",
    )
    try:
        await bot.send_message(
            chat_id=updated.user_telegram_id,
            text=f"ℹ️ Вашу заявку на бронювання #{booking_id} було скасовано.",
        )
    except Exception:
        pass
    await callback.answer("Заявку скасовано")


async def _edit_receipt_message_status(message: Message, status_line_html: str):
    if message.caption is not None:
        base_html = message.html_text or ""
        await message.edit_caption(
            caption=f"{base_html}\n\n{status_line_html}",
            parse_mode="HTML",
            reply_markup=None,
        )
    else:
        base_html = message.html_text or ""
        await message.edit_text(
            text=f"{base_html}\n\n{status_line_html}",
            parse_mode="HTML",
            reply_markup=None,
        )


@router.callback_query(F.data.startswith("receipt:ask_confirm:"))
async def manager_ask_confirm_receipt(callback: CallbackQuery):
    if not is_managers_chat(callback.message.chat.id):
        await callback.answer("⛔ Доступ лише в групі менеджерів", show_alert=True)
        return

    booking_id = int(callback.data.split(":")[2])
    await callback.answer(
        f"⚠️ УВАГА! Перевірте суму та реквізити на квитанції для бронювання #{booking_id}.\n\n"
        "Ви точно хочете підтвердити оплату? Натисніть зелену кнопку нижче.",
        show_alert=True,
    )
    await callback.message.edit_reply_markup(
        reply_markup=get_receipt_confirm_step_kb(booking_id)
    )


@router.callback_query(F.data.startswith("receipt:ask_reject:"))
async def manager_ask_reject_receipt(callback: CallbackQuery):
    if not is_managers_chat(callback.message.chat.id):
        await callback.answer("⛔ Доступ лише в групі менеджерів", show_alert=True)
        return

    booking_id = int(callback.data.split(":")[2])
    await callback.answer(
        f"⚠️ Ви точно хочете відхилити квитанцію для бронювання #{booking_id}?",
        show_alert=True,
    )
    await callback.message.edit_reply_markup(
        reply_markup=get_receipt_reject_step_kb(booking_id)
    )


@router.callback_query(F.data.startswith("receipt:back:"))
async def manager_back_receipt(callback: CallbackQuery):
    if not is_managers_chat(callback.message.chat.id):
        await callback.answer("⛔ Доступ лише в групі менеджерів", show_alert=True)
        return

    booking_id = int(callback.data.split(":")[2])
    await callback.message.edit_reply_markup(
        reply_markup=get_receipt_manager_kb(booking_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("receipt:do_confirm:"))
async def manager_do_confirm_receipt(
    callback: CallbackQuery, booking_service: BookingService
):
    if not is_managers_chat(callback.message.chat.id):
        await callback.answer("⛔ Доступ лише в групі менеджерів", show_alert=True)
        return

    booking_id = int(callback.data.split(":")[2])
    mgr = format_manager_name(callback.from_user)
    res = await booking_service.verify_receipt_by_manager(
        booking_id=booking_id, is_approved=True
    )
    if not res:
        await callback.answer("Бронювання не знайдено", show_alert=True)
        return

    await _edit_receipt_message_status(
        callback.message,
        f"✅ <b>Оплату перевірено (у таблиці встановлено ✅)</b> (опрацював: {mgr})",
    )
    await callback.answer("✅ У таблиці встановлено зелену галочку!")


@router.callback_query(F.data.startswith("receipt:do_reject:"))
async def manager_do_reject_receipt(
    callback: CallbackQuery, booking_service: BookingService
):
    if not is_managers_chat(callback.message.chat.id):
        await callback.answer("⛔ Доступ лише в групі менеджерів", show_alert=True)
        return

    booking_id = int(callback.data.split(":")[2])
    mgr = format_manager_name(callback.from_user)
    res = await booking_service.verify_receipt_by_manager(
        booking_id=booking_id, is_approved=False
    )
    if not res:
        await callback.answer("Бронювання не знайдено", show_alert=True)
        return

    await _edit_receipt_message_status(
        callback.message,
        f"❌ <b>Оплату відхилено (у таблиці встановлено ❌)</b> (опрацював: {mgr})",
    )
    await callback.answer("❌ У таблиці встановлено червоний хрестик!")


# ==================== КЛІЄНТСЬКІ ХЕНДЛЕРИ ====================

WELCOME_PHOTO_PATH = Path(__file__).resolve().parents[2] / "assets" / "welcome.jpg"
_cached_welcome_photo_id: str | None = None


@router.message(CommandStart(), StateFilter("*"))
async def cmd_start(message: Message, state: FSMContext):
    global _cached_welcome_photo_id
    await state.clear()
    first_name = html.escape(
        message.from_user.first_name if message.from_user and message.from_user.first_name else "Друже"
    )
    welcome_text = (
        f"Привіт, <b>{first_name}</b>! Раді бачити тебе в сім’ї <b>STC TRIPS | Student Travel Club</b> 🏔❤️\n\n"
        "Ми створюємо мандрівки, з яких повертаються з новими друзями, сотнями фото та спогадами на все життя! ✨\n\n"
        "<b>У цьому боті ти можеш за 2 хвилини:</b>\n"
        "🏔 <b>Обрати актуальний тур</b> та переглянути детальну програму\n"
        "🎟 <b>Забронювати місце онлайн</b> (самостійно або для всієї компанії)\n"
        "💎 <b>Отримати знижку</b> постійного клієнта, для групи друзів, УБД/дітей або за промокодом\n"
        "❓ <b>Дізнатися відповіді</b> на всі організаційні питання\n\n"
        "👇 <b>Тисни на кнопки меню внизу та гайда назустріч пригодам!</b>"
    )

    if _cached_welcome_photo_id:
        try:
            await message.answer_photo(
                photo=_cached_welcome_photo_id,
                caption=welcome_text,
                parse_mode="HTML",
                reply_markup=get_main_menu_kb(),
            )
            return
        except Exception:
            _cached_welcome_photo_id = None

    if WELCOME_PHOTO_PATH.exists():
        sent = await message.answer_photo(
            photo=FSInputFile(WELCOME_PHOTO_PATH),
            caption=welcome_text,
            parse_mode="HTML",
            reply_markup=get_main_menu_kb(),
        )
        if sent.photo:
            _cached_welcome_photo_id = sent.photo[-1].file_id
    else:
        await message.answer(
            welcome_text,
            parse_mode="HTML",
            reply_markup=get_main_menu_kb(),
        )


@router.message(F.text == "❌ Скасувати", StateFilter("*"))
async def cancel_booking(message: Message, state: FSMContext):
    current_state = await state.get_state()
    await state.clear()

    if current_state is None:
        await message.answer("Ви у головному меню.", reply_markup=get_main_menu_kb())
        return

    await message.answer(
        "🛑 Дію скасовано. Ви повернулися до головного меню.",
        reply_markup=get_main_menu_kb(),
    )


@router.message(F.text == "💎 Статус постійного клієнта")
async def show_loyal_status(message: Message, booking_service: BookingService):
    user_id = message.from_user.id
    is_loyal = await booking_service.is_user_loyal(user_id)
    if is_loyal:
        await message.answer(
            "💎 <b>Ваш статус: Постійний клієнт STC TRIPS ✅</b>\n\n"
            "При бронюванні турів для вас автоматично діє знижка:\n"
            "• <b>-50 грн/ос</b> на 1-денні тури\n"
            "• <b>-150 грн/ос</b> на 2/3-денні тури ❤️",
            parse_mode="HTML",
        )
        return

    user = await booking_service.get_or_update_user(
        telegram_id=user_id,
        username=message.from_user.username,
    )
    if user and user.loyal_request_pending:
        await message.answer(
            "⏳ <b>Ваш запит на отримання статусу постійного клієнта вже на розгляді у менеджера!</b>\n"
            "Щойно менеджер перевірить інформацію та натисне кнопку підтвердження, бот надішле вам сповіщення ❤️",
            parse_mode="HTML",
        )
        return

    await message.answer(
        "💎 <b>Програма лояльності STC TRIPS</b>\n\n"
        "Постійним клієнтом автоматично стає кожен турист, який побував із нами у <b>2 і більше турах</b>!\n"
        "Знижка для постійних клієнтів:\n"
        "• <b>-50 грн/ос</b> у 1-денних турах\n"
        "• <b>-150 грн/ос</b> у 2/3-денних турах\n\n"
        "Якщо ви вже їздили з нами у 2+ тури раніше (до появи цього бота), натисніть кнопку нижче — "
        "менеджер підтвердить ваш статус, і бот запам'ятає вас назавжди!",
        parse_mode="HTML",
        reply_markup=get_loyal_request_start_kb(),
    )


@router.callback_query(F.data == "loyal:start_request")
async def start_loyal_request(callback: CallbackQuery, state: FSMContext):
    await state.set_state(LoyalRequestForm.waiting_for_info)
    await callback.message.answer(
        "📝 Будь ласка, напишіть одним повідомленням:\n"
        "1. Ваше <b>ПІБ та номер телефону</b>\n"
        "2. У яких приблизно турах ви з нами були\n\n"
        "<i>(Наприклад: Іваненко Іван, 0971234567, був на Боржаві та в Тустані)</i>:",
        parse_mode="HTML",
        reply_markup=get_cancel_kb(),
    )
    await callback.answer()


@router.message(LoyalRequestForm.waiting_for_info, F.text)
async def process_loyal_request_info(
    message: Message,
    state: FSMContext,
    bot: Bot,
    booking_service: BookingService,
):
    info_text = message.text.strip()
    if len(info_text) < 5 or len(info_text) > 500:
        await message.answer(
            "⚠️ Повідомлення має містити від 5 до 500 символів (ПІБ, телефон та тури):"
        )
        return

    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username
    await booking_service.get_or_update_user(telegram_id=user_id, username=username)
    await booking_service.set_loyal_status(
        telegram_id=user_id, is_loyal=False, pending=True
    )

    user_tag = f" (@{html.escape(username)})" if username else ""
    try:
        await bot.send_message(
            chat_id=settings.admin_chat_id,
            text=(
                f"💎 <b>Запит на статус Постійного клієнта</b>\n\n"
                f"👤 Користувач: {html.escape(message.from_user.full_name)}{user_tag}\n"
                f"🆔 Telegram ID: <code>{user_id}</code>\n"
                f"📄 Повідомлення від клієнта:\n<i>{html.escape(info_text)}</i>"
            ),
            parse_mode="HTML",
            reply_markup=get_loyal_manager_decision_kb(user_id),
        )
    except Exception:
        logger.exception("Не вдалося надіслати запит на лояльність у групу менеджерів")

    await message.answer(
        "✅ <b>Запит надіслано менеджеру!</b>\n"
        "Щойно менеджер підтвердить ваш статус, вам прийде сповіщення в цей чат ❤️",
        parse_mode="HTML",
        reply_markup=get_main_menu_kb(),
    )


@router.message(F.text == "🏔 Обрати тур")
async def show_tours(message: Message, tour_service: TourService):
    tours = await tour_service.list_available_tours()
    if not tours:
        await message.answer("Наразі актуальних турів немає. Слідкуйте за оновленнями!")
        return
    await message.answer("Оберіть тур зі списку:", reply_markup=get_tours_kb(tours))


@router.message(F.text == "❓ Поширені питання та Умови")
async def show_faq(message: Message, tour_service: TourService):
    faqs = await tour_service.list_faqs()
    await message.answer(
        FAQ_MAIN_TEXT,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=get_faq_menu_kb(faqs),
    )


@router.callback_query(F.data.startswith("faq:"))
async def faq_navigation(callback: CallbackQuery, tour_service: TourService):
    key = callback.data.split(":")[1]
    faqs = await tour_service.list_faqs()

    if key == "main":
        await callback.message.edit_text(
            FAQ_MAIN_TEXT,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=get_faq_menu_kb(faqs),
        )
    elif key.isdigit():
        faq_id = int(key)
        selected = next((f for f in faqs if f.id == faq_id), None)
        if selected:
            await callback.message.edit_text(
                selected.answer_html,
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


# ==================== АНКЕТА БРОНЮВАННЯ (FSM) ====================


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

    await state.clear()
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

    if (
        len(name) > 100
        or len(name.split()) < 2
        or not re.match(r"^[А-Яа-яІіЇїЄєҐґA-Za-z\s\-’']+$", name)
    ):
        await message.answer(
            "⚠️ Будь ласка, введіть коректне ПІБ (мінімум два слова, лише літери, до 100 символів).\nСпробуйте ще раз:"
        )
        return

    await state.update_data(full_name=name)
    await state.set_state(BookingForm.waiting_for_phone)
    await message.answer(
        "📱 Для продовження бронювання натисніть кнопку <b>«📱 Надіслати мій номер»</b> внизу екрана 👇",
        parse_mode="HTML",
        reply_markup=get_phone_kb(),
    )


@router.message(BookingForm.waiting_for_phone, F.contact)
async def process_phone(message: Message, state: FSMContext):
    if message.contact.user_id and message.contact.user_id != message.from_user.id:
        await message.answer(
            "⚠️ Будь ласка, надішліть саме <b>свій</b> номер телефону за допомогою кнопки <b>«📱 Надіслати мій номер»</b> внизу екрана 👇",
            parse_mode="HTML",
            reply_markup=get_phone_kb(),
        )
        return

    phone_raw = message.contact.phone_number or ""
    digits = re.sub(r"\D", "", phone_raw)
    normalized_phone = normalize_phone_number(phone_raw) or (
        f"+{digits}" if digits else phone_raw
    )

    await state.update_data(phone=normalized_phone)
    await state.set_state(BookingForm.waiting_for_age)
    await message.answer(
        "Вкажіть Ваш вік (лише числом):",
        reply_markup=get_cancel_kb(),
    )


@router.message(BookingForm.waiting_for_phone)
async def reject_manual_phone_input(message: Message):
    await message.answer(
        "⚠️ Введення номера з клавіатури вимкнено.\n"
        "Будь ласка, натисніть кнопку <b>«📱 Надіслати мій номер»</b> внизу екрана 👇",
        parse_mode="HTML",
        reply_markup=get_phone_kb(),
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
        "(Введіть цифру, наприклад: 1 — якщо їдете самі, 2 — якщо вдвох, 3–5 — знижка для групок, 6+ — індивідуальний прорахунок)",
        parse_mode="HTML",
    )


async def _ask_ubd_children_step(message: Message, state: FSMContext, tickets_count: int):
    await state.set_state(BookingForm.waiting_for_ubd_children)
    await message.answer(
        "👶🪖 <b>Чи є серед вас діти до 10 років або учасники бойових дій (УБД)?</b>\n"
        "Оберіть кількість таких учасників на клавіатурі нижче (або натисніть «Немає»):",
        parse_mode="HTML",
        reply_markup=get_ubd_children_kb(tickets_count),
    )


async def _ask_notes_step(message: Message, state: FSMContext):
    await state.set_state(BookingForm.waiting_for_notes)
    await message.answer(
        "📝 <b>Чи маєте ви додаткові побажання або нотатку до бронювання?</b>\n"
        "<i>(Наприклад: «мене закачує, посадіть ближче до переду»)</i>\n\n"
        "Напишіть ваше побажання або натисніть кнопку <b>«⏭ Пропустити»</b>:",
        parse_mode="HTML",
        reply_markup=get_skip_or_cancel_kb("⏭ Пропустити"),
    )


@router.message(BookingForm.waiting_for_tickets_count, F.text)
async def process_tickets_count(
    message: Message, state: FSMContext, tour_service: TourService
):
    text = message.text.strip()
    if not text.isdigit() or not (1 <= int(text) <= 59):
        await message.answer("⚠️ Вкажіть коректну кількість місць цифрою:")
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
        await _ask_ubd_children_step(message, state, tickets_count)
    else:
        await state.set_state(BookingForm.waiting_for_other_participants)
        await message.answer(
            f"👥 Ви бронюєте <b>{tickets_count}</b> місць.\n\n"
            f"Будь ласка, вкажіть ПІБ та вік для <b>інших {tickets_count - 1} учасників</b> єдиним повідомленням:",
            parse_mode="HTML",
        )


@router.message(BookingForm.waiting_for_other_participants, F.text)
async def process_others(message: Message, state: FSMContext):
    text = message.text.strip()
    if len(text) < 5 or len(text) > 500:
        await message.answer(
            "⚠️ Вкажіть ПІБ та вік інших учасників (від 5 до 500 символів):"
        )
        return

    await state.update_data(other_participants=text)
    data = await state.get_data()
    tickets_count = data["tickets_count"]

    # Якщо 6 і більше осіб — індивідуальний прорахунок менеджером (переходимо одразу до нотатки)
    if tickets_count >= 6:
        await _ask_notes_step(message, state)
    else:
        await _ask_ubd_children_step(message, state, tickets_count)


@router.message(BookingForm.waiting_for_ubd_children, F.text)
async def process_ubd_children(message: Message, state: FSMContext):
    text = message.text.strip().lower()
    data = await state.get_data()
    tickets_count = data["tickets_count"]

    if text in ("немає", "0", "ні", "нема"):
        ubd_count = 0
    elif text.isdigit() and 1 <= int(text) <= tickets_count:
        ubd_count = int(text)
    else:
        await message.answer(
            f"⚠️ Оберіть «Немає» або введіть цифру від 1 до {tickets_count}:"
        )
        return

    await state.update_data(ubd_children_count=ubd_count)

    if ubd_count > 0:
        await message.answer(
            "⚠️ <b>Зверніть увагу:</b> знижка для дітей та УБД діє лише за умови пред’явлення "
            "підтверджуючого документа гіду при посадці в автобус. Без документа знижка анулюється.",
            parse_mode="HTML",
        )

    await state.set_state(BookingForm.waiting_for_promo_code)
    await message.answer(
        "🎟 <b>Чи є у вас промокод або подарунковий сертифікат?</b>\n"
        "<i>(Зверніть увагу: знижки не сумуються з промокодами та іншими акціями)</i>\n\n"
        "Введіть промокод або натисніть кнопку <b>«⏭ Немає промокоду»</b>:",
        parse_mode="HTML",
        reply_markup=get_skip_or_cancel_kb("⏭ Немає промокоду"),
    )


@router.message(BookingForm.waiting_for_promo_code, F.text)
async def process_promo_code(
    message: Message, state: FSMContext, booking_service: BookingService
):
    text = message.text.strip()
    if text in ("⏭ Немає промокоду", "⏭ Пропустити", "немає", "Немає"):
        await state.update_data(promo_code=None)
        await _ask_notes_step(message, state)
        return

    if len(text) > 50:
        await message.answer("⚠️ Некоректний промокод. Спробуйте ще раз або натисніть «⏭ Немає промокоду»:")
        return

    promo = await booking_service.validate_promo_code(text)
    if not promo:
        await message.answer(
            "⚠️ Такого активного промокоду не знайдено.\n"
            "Перевірте правильність написання або натисніть <b>«⏭ Немає промокоду»</b>:",
            parse_mode="HTML",
        )
        return

    await state.update_data(promo_code=promo.code)
    await message.answer(
        f"✅ Промокод <code>{html.escape(promo.code)}</code> на знижку <b>-{promo.discount_per_person} грн/ос</b> застосовано!",
        parse_mode="HTML",
    )
    await _ask_notes_step(message, state)


@router.message(BookingForm.waiting_for_notes, F.text)
async def process_notes(
    message: Message,
    state: FSMContext,
    bot: Bot,
    booking_service: BookingService,
):
    text = message.text.strip()
    if len(text) > 300:
        await message.answer(
            "⚠️ Нотатка занадто довга (максимум 300 символів). Будь ласка, скоротіть текст або натисніть «⏭ Пропустити»:"
        )
        return
    notes = "немає" if text in ("⏭ Пропустити", "немає", "Немає") else text
    await state.update_data(notes=notes)

    data = await state.get_data()
    tickets_count = data["tickets_count"]

    # Якщо велика компанія (6 і більше осіб) — відправляємо запит у групу менеджерів без фінальної суми!
    if tickets_count >= 6:
        await state.clear()
        username = message.from_user.username if message.from_user else None
        try:
            booking, tour = await booking_service.create_large_group_booking(
                user_telegram_id=message.from_user.id,
                tour_id=data["tour_id"],
                full_name=data["full_name"],
                phone=data["phone"],
                age=data["age"],
                tickets_count=tickets_count,
                other_participants=data["other_participants"],
                notes=notes,
                username=username,
            )
        except ValueError as e:
            await message.answer(
                f"❌ Помилка бронювання: {e}",
                reply_markup=get_main_menu_kb(),
            )
            return

        # Точний текст замовника для 6+ осіб:
        await message.answer(
            "Ого, велика компанія! Для вас діють спеціальні індивідуальні знижки. "
            "Менеджер зв’яжеться з вами найближчим часом для прорахунку",
            reply_markup=get_main_menu_kb(),
        )

        user_tag = f" (@{html.escape(username)})" if username else ""
        try:
            await bot.send_message(
                chat_id=settings.admin_chat_id,
                text=(
                    f"🔥 <b>Запит на індивідуальний прорахунок (Група 6+ осіб | Заявка #{booking.id})</b>\n\n"
                    f"🏔 Тур: <b>{html.escape(tour.title)}</b> ({html.escape(tour.dates)})\n"
                    f"👤 Замовник: <b>{html.escape(booking.full_name)}</b>{user_tag}\n"
                    f"📞 Телефон: {html.escape(booking.phone)} | Вік: {booking.age}\n"
                    f"🎟 Кількість місць: <b>{booking.tickets_count}</b>\n"
                    f"👥 Інші учасники: {html.escape(booking.other_participants)}\n"
                    f"📝 Нотатка: <i>{html.escape(booking.notes)}</i>\n"
                    f"💰 Базова вартість (без знижки): {booking.amount} грн"
                ),
                parse_mode="HTML",
                reply_markup=get_large_group_manager_kb(booking.id),
            )
        except Exception:
            logger.exception(
                "Не вдалося надіслати заявку великої групи #%s у групу менеджерів",
                booking.id,
            )
        return

    await state.set_state(BookingForm.waiting_for_terms_agreement)
    await message.answer(
        "Останній крок перед оплатою 👇",
        reply_markup=get_cancel_kb(),
    )
    await message.answer(
        "Перед переходом до оплати, будь ласка, ознайомтеся та погодьтеся з умовами бронювання:",
        reply_markup=get_terms_agreement_kb(),
    )


@router.message(BookingForm.waiting_for_terms_agreement)
async def process_unexpected_message_during_terms(message: Message):
    await message.answer(
        "👆 Будь ласка, натисніть кнопку <b>«✔️ Погоджуюсь з умовами»</b> у повідомленні вище, "
        "щоб перейти до оплати (або натисніть «❌ Скасувати» внизу).",
        parse_mode="HTML",
        reply_markup=get_cancel_kb(),
    )



@router.message(
    StateFilter(
        BookingForm.waiting_for_full_name,
        BookingForm.waiting_for_age,
        BookingForm.waiting_for_tickets_count,
        BookingForm.waiting_for_other_participants,
        BookingForm.waiting_for_ubd_children,
        BookingForm.waiting_for_promo_code,
        BookingForm.waiting_for_notes,
        LoyalRequestForm.waiting_for_info,
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
    bot: Bot,
    booking_service: BookingService,
):
    data = await state.get_data()
    await state.clear()
    user_id = callback.from_user.id
    username = callback.from_user.username

    try:
        booking, tour, _ = (
            await booking_service.create_booking_with_payment_link(
                user_telegram_id=user_id,
                tour_id=data["tour_id"],
                full_name=data["full_name"],
                phone=data["phone"],
                age=data["age"],
                tickets_count=data["tickets_count"],
                other_participants=data["other_participants"],
                notes=data.get("notes", "немає"),
                ubd_children_count=data.get("ubd_children_count", 0),
                promo_code=data.get("promo_code"),
                username=username,
            )
        )
    except ValueError as e:
        await callback.message.answer(
            f"❌ Помилка бронювання: {e}",
            reply_markup=get_main_menu_kb(),
        )
        await callback.answer()
        return

    base_amount = tour.price * booking.tickets_count
    discount_line = ""
    if booking.discount_info and booking.discount_info != "немає":
        discount_line = (
            f"💰 Базова вартість: <s>{base_amount} грн</s>\n"
            f"🏷 Застосована знижка: <b>{html.escape(booking.discount_info)}</b>\n"
        )

    note_line = (
        f"📝 Ваша нотатка: <i>{html.escape(booking.notes)}</i>\n"
        if booking.notes and booking.notes != "немає"
        else ""
    )

    first_name = html.escape(callback.from_user.first_name or "Друже")
    deadline_str = (datetime.now(KYIV_TZ) + timedelta(minutes=15)).strftime("%H:%M")
    details_msg = (
        f"{first_name}, привіт, раді бачити ❤️\n\n"
        f"Бронювання туру: <b>{html.escape(tour.title)}</b>\n"
        f"👥 Кількість місць: {booking.tickets_count}\n"
        f"{discount_line}"
        f"💳 <b>Вартість до сплати: {booking.amount} грн</b>\n"
        f"{note_line}"
        f"⏳ Бронь місць діє до: <b>{deadline_str}</b> (15 хв на оплату)\n"
    )

    await state.set_state(BookingForm.waiting_for_receipt)
    await state.update_data(receipt_booking_id=booking.id)

    await callback.message.answer(
        "✅ Анкету успішно сформовано!",
        reply_markup=get_cancel_kb(),
    )

    await send_iban_payment_instructions(
        bot=bot,
        chat_id=callback.message.chat.id,
        summary_html=details_msg,
    )
    await callback.answer()


async def _delayed_receipt_confirmation(
    bot: Bot,
    user_telegram_id: int,
    booking_id: int,
    tour_title: str,
    tour_dates: str,
    delay_seconds: int = 60,
):
    await asyncio.sleep(delay_seconds)
    safe_title = html.escape(tour_title)
    safe_dates = html.escape(tour_dates)
    try:
        await bot.send_message(
            chat_id=user_telegram_id,
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
            "Не вдалося надіслати відкладене підтвердження туристу %s (бронювання #%s)",
            user_telegram_id,
            booking_id,
        )


@router.message(
    F.chat.type == "private",
    F.photo | F.document,
    StateFilter(BookingForm.waiting_for_receipt, None),
)
async def process_payment_receipt(
    message: Message,
    state: FSMContext,
    bot: Bot,
    booking_service: BookingService,
):
    data = await state.get_data()
    receipt_booking_id = data.get("receipt_booking_id")
    user_id = message.from_user.id

    res = await booking_service.mark_receipt_submitted(
        booking_id=receipt_booking_id,
        user_telegram_id=user_id,
    )
    if not res:
        await message.answer(
            "ℹ️ У вас наразі немає активного очікуючого бронювання для прикріплення квитанції.\n"
            "Оберіть тур у меню нижче або напишіть нашому менеджеру 👇",
            reply_markup=get_main_menu_kb(),
        )
        return

    await state.clear()
    booking, tour = res
    user_tag = f" (@{html.escape(booking.username)})" if booking.username else ""

    caption_html = (
        f"🧾 <b>Нове бронювання з квитанцією (#{booking.id})</b>\n"
        f"📋 <i>Додано в таблицю зі статусом 🌹 (очікує звірки менеджером)</i>\n\n"
        f"🏔 Тур: <b>{html.escape(tour.title)}</b> ({html.escape(tour.dates)})\n"
        f"👤 Турист: <b>{html.escape(booking.full_name)}</b>{user_tag}\n"
        f"📞 Тел: {html.escape(booking.phone)} | Вік: {booking.age}\n"
        f"🎟 Кількість місць: <b>{booking.tickets_count}</b>\n"
        f"👥 Інші учасники: {html.escape(booking.other_participants)}\n"
        f"🏷 Знижки / Пільги: <b>{html.escape(booking.discount_info)}</b>\n"
        f"📝 Нотатка: <i>{html.escape(booking.notes)}</i>\n"
        f"💳 <b>Сума до сплати: {booking.amount} грн</b>"
    )

    try:
        if message.photo:
            await bot.send_photo(
                chat_id=settings.admin_chat_id,
                photo=message.photo[-1].file_id,
                caption=caption_html,
                parse_mode="HTML",
                reply_markup=get_receipt_manager_kb(booking.id),
            )
        elif message.document:
            await bot.send_document(
                chat_id=settings.admin_chat_id,
                document=message.document.file_id,
                caption=caption_html,
                parse_mode="HTML",
                reply_markup=get_receipt_manager_kb(booking.id),
            )
    except Exception:
        logger.exception(
            "Не вдалося переслати квитанцію бронювання #%s у чат менеджерів",
            booking.id,
        )

    await message.answer(
        "⏳ <b>Дякуємо! Вашу квитанцію отримано, обробляємо інформацію...</b>",
        parse_mode="HTML",
        reply_markup=get_main_menu_kb(),
    )

    asyncio.create_task(
        _delayed_receipt_confirmation(
            bot=bot,
            user_telegram_id=booking.user_telegram_id,
            booking_id=booking.id,
            tour_title=tour.title,
            tour_dates=tour.dates,
            delay_seconds=60,
        )
    )


@router.message(BookingForm.waiting_for_receipt)
async def process_unexpected_during_receipt(message: Message):
    await message.answer(
        "📸 Будь ласка, надішліть <b>фото (скріншот) або PDF-файл квитанції</b> про оплату "
        "(або натисніть «❌ Скасувати», щоб повернутися в головне меню).",
        parse_mode="HTML",
        reply_markup=get_cancel_kb(),
    )


@router.message(F.chat.type == "private", StateFilter(None))
async def fallback_private_menu(message: Message):
    await message.answer(
        "Оберіть потрібний розділ у меню нижче 👇",
        reply_markup=get_main_menu_kb(),
    )

