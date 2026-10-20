from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from src.domain.entities import TourEntity
from src.config import settings


def get_main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏔 Обрати тур")],
            [
                KeyboardButton(text="❓ Поширені питання та Умови"),
                KeyboardButton(text="💬 Зв'язок з менеджером"),
            ],
        ],
        resize_keyboard=True,
    )


def get_tours_kb(tours: list[TourEntity]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for tour in tours:
        builder.button(
            text=f"{tour.title} | {tour.dates}", callback_data=f"tour:{tour.id}"
        )
    builder.adjust(1)
    return builder.as_markup()


def get_tour_action_kb(tour_id: int, program_url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🗺 Читати програму туру", url=program_url)
    builder.button(text="✅ Забронювати місце", callback_data=f"book:{tour_id}")
    builder.adjust(1)
    return builder.as_markup()


def get_terms_agreement_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📄 Договір публічної оферти", url=settings.public_offer_url)
    builder.button(text="📄 Умови повернення коштів", url=settings.refund_policy_url)
    builder.button(text="✔️ Погоджуюсь з умовами", callback_data="agree_terms")
    builder.adjust(1)
    return builder.as_markup()


def get_payment_kb(payment_url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="💳 Оплатити тур (Приват24 / Apple Pay / Картка)", url=payment_url
    )
    builder.adjust(1)
    return builder.as_markup()


def get_cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Скасувати")]
        ],
        resize_keyboard=True,
    )
