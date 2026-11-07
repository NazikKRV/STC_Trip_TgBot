from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from src.config import settings
from src.domain.entities import TourEntity


def get_main_menu_kb(is_admin: bool = False) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="🏔 Обрати тур")],
        [
            KeyboardButton(text="❓ Поширені питання та Умови"),
            KeyboardButton(text="💬 Зв'язок з менеджером"),
        ],
    ]
    if is_admin:
        keyboard.append([KeyboardButton(text="⚙️ Адмін-панель")])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
    )


def get_cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Скасувати")]],
        resize_keyboard=True,
    )


def get_phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Надіслати мій номер", request_contact=True)],
            [KeyboardButton(text="❌ Скасувати")],
        ],
        resize_keyboard=True,
    )


def get_tours_kb(tours: list[TourEntity]) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=f"{tour.title} | {tour.dates}",
                callback_data=f"tour:{tour.id}",
            )
        ]
        for tour in tours
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_tour_action_kb(tour_id: int, program_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗺 Детальна програма туру", url=program_url
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Забронювати місце", callback_data=f"book:{tour_id}"
                )
            ],
        ]
    )


def get_terms_agreement_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📄 Договір публічної оферти",
                    url=settings.public_offer_url,
                )
            ],
            [
                InlineKeyboardButton(
                    text="📄 Умови повернення коштів",
                    url=settings.refund_policy_url,
                )
            ],
            [
                InlineKeyboardButton(
                    text="✔️ Погоджуюсь з умовами", callback_data="agree_terms"
                )
            ],
        ]
    )


def get_payment_kb(payment_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 Оплатити тур (Приват24 / Apple Pay / Картка)",
                    url=payment_url,
                )
            ]
        ]
    )


def get_faq_menu_kb(faq_items: dict[str, tuple[str, str]]) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text="📄 Договір оферти", url=settings.public_offer_url
            ),
            InlineKeyboardButton(
                text="📄 Умови повернення", url=settings.refund_policy_url
            ),
        ]
    ]
    for key, (question_title, _) in faq_items.items():
        buttons.append(
            [
                InlineKeyboardButton(
                    text=question_title, callback_data=f"faq:{key}"
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_faq_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Назад до всіх питань", callback_data="faq:main"
                )
            ]
        ]
    )


def get_admin_panel_kb(tours: list[TourEntity]) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text="🔄 Синхронізувати розклад з Google Таблицею",
                callback_data="admin:sync",
            )
        ]
    ]
    for tour in tours:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"🏔 #{tour.id} {tour.title} ({tour.dates})",
                    callback_data=f"admin:tour:{tour.id}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_tour_kb(tour_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👥 Список оплачених учасників",
                    callback_data=f"admin:group:{tour_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📨 Розіслати посилання на чат групі",
                    callback_data=f"admin:send_chat_confirm:{tour_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад до адмін-панелі",
                    callback_data="admin:main",
                )
            ],
        ]
    )


def get_admin_confirm_chat_kb(tour_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Так, розіслати зараз",
                    callback_data=f"admin:send_chat_run:{tour_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Скасувати",
                    callback_data=f"admin:tour:{tour_id}",
                ),
            ]
        ]
    )
