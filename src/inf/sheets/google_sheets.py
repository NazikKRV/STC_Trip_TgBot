import asyncio
import re
from datetime import datetime
import gspread
from src.domain.entities import TourEntity, BookingEntity


def _parse_int(value: object, default: int = 0) -> int:
    digits = re.sub(r"[^\d]", "", str(value or ""))
    return int(digits) if digits else default


def _sanitize_sheet_title(title: str, dates: str) -> str:
    raw = f"{title[:30]} ({dates[:15]})"
    # Заборонені символи у назвах вкладок Google Sheets: [ ] * ? / \ :
    cleaned = re.sub(r"[\[\]\*\?\/\\:]", "-", raw)
    cleaned = cleaned.strip().strip("'")
    return cleaned[:95] or "Тур"


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
                title = str(row.get("Назва") or "").strip()
                if not title:
                    continue
                price = _parse_int(row.get("Ціна"), default=0)
                if price <= 0:
                    continue
                tours.append(
                    TourEntity(
                        id=None,
                        title=title,
                        dates=str(row.get("Дати") or "").strip(),
                        price=price,
                        program_url=str(row.get("Програма (URL)") or "").strip(),
                        included_details=str(row.get("Що входить") or "").strip(),
                        payment_deadline=str(row.get("Дедлайн оплати") or "").strip(),
                        chat_link=str(row.get("Посилання на чат") or "").strip(),
                        max_seats=_parse_int(row.get("Макс місць"), default=59),
                        is_active=True,
                    )
                )
            return tours

        return await asyncio.to_thread(_sync_fetch)

    async def append_paid_booking(self, tour: TourEntity, booking: BookingEntity) -> None:
        def _sync_append():
            sh = self._get_spreadsheet()
            sheet_title = _sanitize_sheet_title(tour.title, tour.dates)

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
                    "Telegram ID",
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
