import re
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
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
)

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"{message.from_user.first_name}, привіт, раді бачити ❤️\n\n"
        "Обирай актуальний тур у меню нижче та бронюй місце онлайн без черг!",
        reply_markup=get_main_menu_kb(),
    )


@router.message(F.text == "❌ Скасувати")
async def cancel_booking(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return

    await state.clear()
    await message.answer(
        "🛑 Бронювання скасовано. Ви повернулися до головного меню.",
        reply_markup=get_main_menu_kb(),
    )


@router.message(Command("sync_tours"))
async def cmd_sync_tours(message: Message, tour_service: TourService):
    if message.from_user.id != settings.admin_chat_id:
        return

    wait_msg = await message.answer("🔄 Синхронізую розклад із Google Таблицею...")
    try:
        from src.inf.sheets.google_sheets import GoogleSheetsService
        sheets = GoogleSheetsService(settings.google_credentials_path, settings.google_sheet_id)
        count = await tour_service.sync_from_sheets(sheets)
        await wait_msg.edit_text(f"✅ Успішно синхронізовано! Актуальних турів у базі: <b>{count}</b>",
                                     parse_mode="HTML")
    except Exception as e:
        await wait_msg.edit_text(f"❌ Помилка синхронізації: {e}")


@router.message(F.text == "🏔 Обрати тур")
async def show_tours(message: Message, tour_service: TourService):
    tours = await tour_service.list_available_tours()
    if not tours:
        await message.answer("Наразі актуальних турів немає. Слідкуйте за оновленнями!")
        return
    await message.answer("Оберіть тур зі списку:", reply_markup=get_tours_kb(tours))


@router.message(F.text == "❓ Поширені питання та Умови")
async def show_faq(message: Message):
    text = (
        "📌 <b>Корисна інформація для туристів:</b>\n\n"
        f"📃 Договір публічної оферти: {settings.public_offer_url}\n"
        f"📃 Опис умов повернення коштів: {settings.refund_policy_url}"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "💬 Зв'язок з менеджером")
async def contact_manager(message: Message):
    await message.answer(
        f"Маєте додаткові запитання? Напишіть нашому менеджеру: @{settings.manager_username}"
    )


@router.callback_query(F.data.startswith("tour:"))
async def tour_details(callback: CallbackQuery, tour_service: TourService):
    tour_id = int(callback.data.split(":")[1])
    tour = await tour_service.get_tour(tour_id)
    if not tour:
        await callback.answer("Тур не знайдено", show_alert=True)
        return

    real_left = await tour_service.get_remaining_seats(tour_id)
    seats_info = tour_service.format_marketing_seats_text(real_left)

    text = (
        f"<b>{tour.title}</b>\n"
        f"🗺 програма: {tour.program_url}\n\n"
        f"🗓 {tour.dates}\n"
        f"💳 Вартість: {tour.price} грн/особи\n"
        f"{seats_info}\n\n"
        f"<b>У неї входить:</b>\n{tour.included_details}"
    )
    await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=get_tour_action_kb(tour.id, tour.program_url),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("book:"))
async def start_booking(callback: CallbackQuery, state: FSMContext, tour_service: TourService):
    tour_id = int(callback.data.split(":")[1])
    real_left = await tour_service.get_remaining_seats(tour_id)

    if real_left <= 0:
        await callback.answer("😔 На жаль, усі місця на цей тур вже розкуплено!", show_alert=True)
        return

    await state.update_data(tour_id=tour_id)
    await state.set_state(BookingForm.waiting_for_full_name)

    await callback.message.answer(
        "Введіть Ваше ПІБ (Прізвище, Ім'я, По батькові):",
        reply_markup=get_cancel_kb(),
    )
    await callback.answer()


@router.message(BookingForm.waiting_for_full_name)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()

    if len(name.split()) < 2 or not re.match(r"^[А-Яа-яІіЇїЄєҐґA-Za-z\s\-']+$", name):
        await message.answer("⚠️ Будь ласка, введіть повне ПІБ (мінімум два слова, лише літери).\nСпробуйте ще раз:")
        return

    await state.update_data(full_name=name)
    await state.set_state(BookingForm.waiting_for_phone)
    await message.answer("Введіть Ваш контактний номер телефону (наприклад, +380991234567):")


@router.message(BookingForm.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    phone_raw = message.text.strip()
    phone_clean = phone_raw.replace(" ", "").replace("-", "")

    if not re.match(r"^(?:\+380|380|0)\d{9}$", phone_clean):
        await message.answer("⚠️ Некоректний формат телефону.\nБудь ласка, введіть номер у форматі +380... або 099...:")
        return

    if phone_clean.startswith("0"):
        phone_clean = "+38" + phone_clean
    elif phone_clean.startswith("380"):
        phone_clean = "+" + phone_clean

    await state.update_data(phone=phone_clean)
    await state.set_state(BookingForm.waiting_for_age)
    await message.answer("Вкажіть Ваш вік (лише числом):")


@router.message(BookingForm.waiting_for_age)
async def process_age(message: Message, state: FSMContext):
    if not message.text.isdigit() or not (14 <= int(message.text) <= 100):
        await message.answer("⚠️ Вкажіть реальний вік цифрою (наприклад: 24):")
        return

    await state.update_data(age=int(message.text))
    await state.set_state(BookingForm.waiting_for_tickets_count)
    await message.answer(
        "🎟 <b>Скільки всього місць ви хочете забронювати?</b>\n"
        "(Введіть цифру, наприклад: 1 — якщо їдете самі, 2 — якщо вдвох і т.д.)",
        parse_mode="HTML",
    )


@router.message(BookingForm.waiting_for_tickets_count)
async def process_tickets_count(message: Message, state: FSMContext, tour_service: TourService):
    if not message.text.isdigit() or not (1 <= int(message.text) <= 20):
        await message.answer("⚠️ Вкажіть цифру від 1 до 20:")
        return

    tickets_count = int(message.text)
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


@router.message(BookingForm.waiting_for_other_participants)
async def process_others(message: Message, state: FSMContext):
    if len(message.text) < 5:
        await message.answer("⚠️ Напишіть детальніше (ПІБ та вік інших учасників):")
        return

    await state.update_data(other_participants=message.text.strip())
    await state.set_state(BookingForm.waiting_for_terms_agreement)
    await message.answer(
        "Перед переходом до оплати, будь ласка, ознайомтеся та погодьтеся з умовами бронювання:",
        reply_markup=get_terms_agreement_kb(),
    )


@router.callback_query(BookingForm.waiting_for_terms_agreement, F.data == "agree_terms")
async def process_terms_and_send_payment_link(
    callback: CallbackQuery,
    state: FSMContext,
    booking_service: BookingService,
):
    data = await state.get_data()
    await state.clear()

    try:
        booking, tour, payment_url = await booking_service.create_booking_with_payment_link(
            user_telegram_id=callback.from_user.id,
            tour_id=data["tour_id"],
            full_name=data["full_name"],
            phone=data["phone"],
            age=data["age"],
            tickets_count=data["tickets_count"],
            other_participants=data["other_participants"],
        )
    except ValueError as e:
        await callback.message.answer(
            f"❌ Помилка бронювання: {e}",
            reply_markup=get_main_menu_kb(),
        )
        await callback.answer()
        return

    details_msg = (
        f"{callback.from_user.first_name}, привіт, раді бачити ❤️\n\n"
        f"Бронювання туру: <b>{tour.title}</b>\n"
        f"👥 Кількість місць: {booking.tickets_count}\n"
        f"💳 <b>Вартість до сплати: {booking.amount} грн</b>\n\n"
        f"⏳ Дедлайн оплати: {tour.payment_deadline}\n"
    )

    await callback.message.answer(
        "✅ Анкету успішно сформовано!",
        reply_markup=get_main_menu_kb(),
    )

    await callback.message.answer(
        details_msg,
        parse_mode="HTML",
        reply_markup=get_payment_kb(payment_url),
    )
    await callback.answer()


@router.message(Command("send_chat_link"))
async def broadcast_chat_link(
    message: Message,
    bot: Bot,
    tour_service: TourService,
    booking_service: BookingService,
):
    """Команда адміна (/send_chat_link 1) для розсилки чату підтвердженій групі."""
    if message.from_user.id != settings.admin_chat_id:
        return

    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Використання: /send_chat_link <id_туру>")
        return

    tour_id = int(parts[1])
    tour = await tour_service.get_tour(tour_id)
    bookings = await booking_service.get_group_list(tour_id)

    sent_count = 0
    for b in bookings:
        await bot.send_message(
            chat_id=b.user_telegram_id,
            text=(
                f"🚌 Вже скоро вирушаємо у тур <b>{tour.title}</b>!\n"
                f"Приєднуйтесь до організаційного чату нашої групи: {tour.chat_link}"
            ),
            parse_mode="HTML",
        )
        sent_count += 1

    await message.answer(
        f"✅ Посилання на чат успішно розіслано ({sent_count} учасникам)."
    )

