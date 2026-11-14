from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from src.config import settings
from src.domain.entities import TourEntity, FaqEntity


def get_main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏔 Обрати тур")],
            [
                KeyboardButton(text="💎 Статус постійного клієнта"),
                KeyboardButton(text="❓ Поширені питання та Умови"),
            ],
            [KeyboardButton(text="💬 Зв'язок з менеджером")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def get_managers_group_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="⚙️ Панель управління"),
                KeyboardButton(text="🔄 Синхронізувати таблицю"),
            ]
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def get_cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Скасувати")]],
        resize_keyboard=True,
    )


def get_skip_or_cancel_kb(skip_text: str = "⏭ Пропустити") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=skip_text)],
            [KeyboardButton(text="❌ Скасувати")],
        ],
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


def get_ubd_children_kb(max_count: int) -> ReplyKeyboardMarkup:
    row = [KeyboardButton(text="Немає")]
    numbers_row = [KeyboardButton(text=str(i)) for i in range(1, max_count + 1)]
    return ReplyKeyboardMarkup(
        keyboard=[
            row,
            numbers_row,
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


def get_faq_menu_kb(faqs: list[FaqEntity]) -> InlineKeyboardMarkup:
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
    for faq in faqs:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=faq.button_title, callback_data=f"faq:{faq.id}"
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


def get_loyal_request_start_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🙋‍♂️ Я вже їздив(ла) у 2+ тури — подати запит менеджеру",
                    callback_data="loyal:start_request",
                )
            ]
        ]
    )


def get_loyal_manager_decision_kb(user_telegram_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Підтвердити постійного клієнта",
                    callback_data=f"loyal:approve:{user_telegram_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Відхилити запит",
                    callback_data=f"loyal:reject:{user_telegram_id}",
                )
            ],
        ]
    )


def get_large_group_manager_kb(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 Виставити суму зі знижкою (надіслати реквізити IBAN)",
                    callback_data=f"mgr_group:price:{booking_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Опрацьовано (підтвердити оплату вручну)",
                    callback_data=f"mgr_group:confirm_ask:{booking_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Скасувати заявку",
                    callback_data=f"mgr_group:cancel_ask:{booking_id}",
                )
            ],
        ]
    )


def get_large_group_confirm_step_kb(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🟢 ТАК, точно підтвердити оплату (#{booking_id})",
                    callback_data=f"mgr_group:confirm:{booking_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data=f"mgr_group:back:{booking_id}",
                )
            ],
        ]
    )


def get_large_group_cancel_step_kb(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🔴 ТАК, точно скасувати заявку (#{booking_id})",
                    callback_data=f"mgr_group:cancel:{booking_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data=f"mgr_group:back:{booking_id}",
                )
            ],
        ]
    )


def get_receipt_manager_kb(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Підтвердити оплату (поставити ✅ в таблиці)",
                    callback_data=f"receipt:ask_confirm:{booking_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Відхилити оплату (поставити ❌ в таблиці)",
                    callback_data=f"receipt:ask_reject:{booking_id}",
                )
            ],
        ]
    )


def get_receipt_confirm_step_kb(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🟢 ТАК, поставити ✅ в таблиці (#{booking_id})",
                    callback_data=f"receipt:do_confirm:{booking_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data=f"receipt:back:{booking_id}",
                )
            ],
        ]
    )


def get_receipt_reject_step_kb(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🔴 ТАК, поставити ❌ в таблиці (#{booking_id})",
                    callback_data=f"receipt:do_reject:{booking_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data=f"receipt:back:{booking_id}",
                )
            ],
        ]
    )


def get_admin_panel_kb(tours: list[TourEntity]) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text="🔄 Синхронізувати з Google Таблицею (Тури, FAQ, Промо)",
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
