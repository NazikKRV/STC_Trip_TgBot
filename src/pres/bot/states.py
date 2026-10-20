from aiogram.fsm.state import StatesGroup, State


class BookingForm(StatesGroup):
    waiting_for_full_name = State()
    waiting_for_phone = State()
    waiting_for_age = State()
    waiting_for_tickets_count = State()
    waiting_for_other_participants = State()
    waiting_for_terms_agreement = State()
