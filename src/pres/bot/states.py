from aiogram.fsm.state import StatesGroup, State


class BookingForm(StatesGroup):
    waiting_for_full_name = State()
    waiting_for_phone = State()
    waiting_for_age = State()
    waiting_for_tickets_count = State()
    waiting_for_other_participants = State()
    waiting_for_ubd_children = State()
    waiting_for_promo_code = State()
    waiting_for_notes = State()
    waiting_for_terms_agreement = State()
    waiting_for_receipt = State()


class LoyalRequestForm(StatesGroup):
    waiting_for_info = State()


class ManagerCustomPriceForm(StatesGroup):
    waiting_for_custom_amount = State()
