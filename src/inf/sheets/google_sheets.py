import asyncio
from datetime import datetime
import gspread
from src.config import settings
from src.domain.entities import TourEntity, BookingEntity


class GoogleSheetsService:
    def __init__(self, credentials_path: str, sheet_id: str):
        self._credentials_path = credentials_path
        self._sheet_id = sheet_id

    def _get_spreadsheet(self) -> gspread.Spreadsheet:
        gc = gspread.service_account(filename=self._credentials_path)
        return gc.open_by_key(self._sheet_id)

    async def fetch_tours_from_sheet(self) -> list[TourEntity]:
        def _sync_fetch():
            sh = self._get_spreadsheet()
            ws = sh.worksheet("Розклад")
            records = ws.get_all_records()
            tours = []
            for row in records:
                if not row.get("Назва"):
                    continue
                tours.append(
                    TourEntity(
                        id=None,
                        title=str(row["Назва"]).strip(),
                        dates=str(row["Дати"]).strip(),
                        price=int(row["Ціна"]),
                        program_url=str(row["Програма (URL)"]).strip(),
                        included_details=str(row["Що входить"]).strip(),
                        payment_deadline=str(row["Дедлайн оплати"]).strip(),
                        chat_link=str(row["Посилання на чат"]).strip(),
                        max_seats=int(row.get("Макс місць") or 59),
                        is_active=True,
                    )
                )
            return tours

        return await asyncio.to_thread(_sync_fetch)

    async def append_paid_booking(self, tour: TourEntity, booking: BookingEntity) -> None:
        def _sync_append():
            sh = self._get_spreadsheet()
            sheet_title = f"{tour.title[:30]} ({tour.dates[:15]})".replace("/", "-").replace(":", "-")

            try:
                ws = sh.worksheet(sheet_title)
            except gspread.WorksheetNotFound:
                ws = sh.add_worksheet(title=sheet_title, rows=100, cols=10)
                ws.append_row([
                    "ID Бронювання",
                    "Дата оплати",
                    "ПІБ",
                    "Телефон",
                    "Вік",
                    "Кількість місць",
                    "Інші учасники",
                    "Сума (грн)",
                    "ID транзакції LiqPay",
                    "Telegram ID"
                ])

            ws.append_row([
                booking.id,
                datetime.now().strftime("%d.%m.%Y %H:%M"),
                booking.full_name,
                booking.phone,
                booking.age,
                booking.tickets_count,
                booking.other_participants,
                booking.amount,
                booking.transaction_id or "",
                booking.user_telegram_id,
            ])

        await asyncio.to_thread(_sync_append)