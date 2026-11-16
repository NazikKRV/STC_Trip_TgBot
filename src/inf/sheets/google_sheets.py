import asyncio
import re
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import gspread
from src.domain.entities import (
    TourEntity,
    BookingEntity,
    FaqEntity,
    PromoCodeEntity,
)

try:
    KYIV_TZ = ZoneInfo("Europe/Kyiv")
except ZoneInfoNotFoundError:
    KYIV_TZ = datetime.now().astimezone().tzinfo or timezone(timedelta(hours=2))


def _parse_int(value: object, default: int = 0) -> int:
    digits = re.sub(r"[^\d]", "", str(value or ""))
    return int(digits) if digits else default


def _extract_short_date(dates: str) -> str:
    """Відрізає час у дужках із поля Дати, напр. '20 листопада (08:00 - 22:30)' -> '20 листопада'."""
    base = re.sub(r"\s*\(.*?\)", "", str(dates or "")).strip()
    base = re.sub(r"\s+", " ", base)
    return base or str(dates or "").strip()


def _sanitize_sheet_title(title: str, dates: str) -> str:
    clean_title = re.sub(r"\s+", " ", str(title or "").strip())
    short_date = _extract_short_date(dates)
    raw = f"{clean_title[:60]} ({short_date[:30]})" if short_date else clean_title[:90]
    cleaned = re.sub(r"[\[\]\*\?\/\\:]", "-", raw)
    cleaned = cleaned.strip().strip("'")
    return cleaned[:95] or "Тур"


def _sanitize_cell(value: object) -> str:
    return str(value or "").strip()


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

                raw_days = (
                    row.get("Кількість днів")
                    or row.get("Тривалість (днів)")
                    or row.get("Днів")
                )
                if raw_days:
                    duration_days = max(1, _parse_int(raw_days, default=1))
                else:
                    duration_days = 1

                tours.append(
                    TourEntity(
                        id=None,
                        title=title,
                        dates=str(row.get("Дати") or "").strip(),
                        price=price,
                        program_url=str(row.get("Програма (URL)") or "").strip(),
                        included_details=str(row.get("Що входить") or "").strip(),
                        payment_deadline="15 хвилин",
                        chat_link=str(row.get("Посилання на чат") or "").strip(),
                        max_seats=_parse_int(row.get("Макс місць"), default=59),
                        duration_days=duration_days,
                        is_active=True,
                    )
                )
            return tours

        return await asyncio.to_thread(_sync_fetch)

    async def sync_faqs_with_sheet(
        self, default_faqs: list[FaqEntity]
    ) -> list[FaqEntity]:
        def _sync_faqs():
            sh = self._get_spreadsheet()
            try:
                ws = sh.worksheet("FAQ")
                records = ws.get_all_records()
                faqs = []
                for idx, row in enumerate(records, start=1):
                    btn = str(row.get("Питання (кнопка)") or "").strip()
                    ans = str(row.get("Відповідь") or "").strip()
                    if btn and ans:
                        faqs.append(
                            FaqEntity(
                                id=idx,
                                button_title=btn,
                                answer_html=ans,
                                sort_order=idx,
                            )
                        )
                if faqs:
                    return faqs
            except gspread.WorksheetNotFound:
                ws = sh.add_worksheet(title="FAQ", rows=30, cols=2)
                rows_to_insert = [["Питання (кнопка)", "Відповідь"]]
                for f in default_faqs:
                    rows_to_insert.append([f.button_title, f.answer_html])
                ws.append_rows(rows_to_insert)

            return default_faqs

        return await asyncio.to_thread(_sync_faqs)

    async def sync_promos_with_sheet(self) -> list[PromoCodeEntity]:
        def _sync_promos():
            sh = self._get_spreadsheet()
            try:
                ws = sh.worksheet("Промокоди")
            except gspread.WorksheetNotFound:
                ws = sh.add_worksheet(title="Промокоди", rows=50, cols=2)
                ws.append_row(["Промокод", "Знижка з особи (грн)"])

            records = ws.get_all_records()
            promos = []
            for row in records:
                code = str(row.get("Промокод") or "").strip().upper()
                discount = _parse_int(row.get("Знижка з особи (грн)"), default=0)
                if code and discount > 0:
                    promos.append(
                        PromoCodeEntity(
                            code=code,
                            discount_per_person=discount,
                            is_active=True,
                        )
                    )
            return promos

        return await asyncio.to_thread(_sync_promos)

    def _find_or_create_tour_worksheet(
        self, sh: gspread.Spreadsheet, tour: TourEntity, create_if_missing: bool = True
    ) -> gspread.Worksheet | None:
        sheet_title = _sanitize_sheet_title(tour.title, tour.dates)
        headers = [
            "ID Бронювання",
            "Дата оплати",
            "ПІБ",
            "Телефон",
            "Вік",
            "Кількість місць",
            "Інші учасники",
            "Знижки / Пільги (УБД, Діти)",
            "Нотатка / Побажання",
            "Сума (грн)",
            "Підтвердження оплати",
            "Telegram (@нік)",
        ]

        ws = None
        try:
            ws = sh.worksheet(sheet_title)
        except gspread.WorksheetNotFound:
            clean_title_prefix = re.sub(
                r"[\[\]\*\?\/\\:]", "-", re.sub(r"\s+", " ", tour.title.strip())
            )[:30].lower()
            short_date_lower = _extract_short_date(tour.dates).lower()
            for candidate in sh.worksheets():
                cand_name = candidate.title.strip().lower()
                if cand_name in ("розклад", "faq", "промокоди"):
                    continue
                if cand_name.startswith(clean_title_prefix) and (
                    not short_date_lower or short_date_lower in cand_name
                ):
                    ws = candidate
                    try:
                        if candidate.title != sheet_title:
                            candidate.update_title(sheet_title)
                    except Exception:
                        pass
                    break

        if ws is not None:
            existing_headers = ws.row_values(1)
            if existing_headers != headers:
                if ws.col_count < len(headers):
                    ws.add_cols(len(headers) - ws.col_count)
                ws.update("A1:L1", [headers])
            return ws

        if not create_if_missing:
            return None

        ws = sh.add_worksheet(title=sheet_title, rows=100, cols=12)
        ws.append_row(headers)
        return ws

    async def append_paid_booking(
        self, tour: TourEntity, booking: BookingEntity
    ) -> None:
        def _sync_append():
            sh = self._get_spreadsheet()
            ws = self._find_or_create_tour_worksheet(sh, tour, create_if_missing=True)

            tg_nick = f"@{booking.username}" if booking.username else "прихований"
            ws.append_row(
                [
                    booking.id,
                    datetime.now(KYIV_TZ).strftime("%d.%m.%Y %H:%M"),
                    _sanitize_cell(booking.full_name),
                    _sanitize_cell(booking.phone),
                    booking.age,
                    booking.tickets_count,
                    _sanitize_cell(booking.other_participants),
                    _sanitize_cell(booking.discount_info),
                    _sanitize_cell(booking.notes),
                    booking.amount,
                    _sanitize_cell(booking.transaction_id or "🌹"),
                    _sanitize_cell(tg_nick),
                ],
                value_input_option="RAW",
            )

        await asyncio.to_thread(_sync_append)

    async def update_booking_payment_mark(
        self, tour: TourEntity, booking: BookingEntity, mark: str
    ) -> None:
        def _sync_update_mark():
            sh = self._get_spreadsheet()
            ws = self._find_or_create_tour_worksheet(sh, tour, create_if_missing=True)
            id_col = ws.col_values(1)
            target_row = None
            for idx, val in enumerate(id_col, start=1):
                if idx == 1:
                    continue
                if str(val).strip() == str(booking.id):
                    target_row = idx
                    break

            if target_row is not None:
                ws.update_cell(target_row, 11, mark)
            else:
                tg_nick = f"@{booking.username}" if booking.username else "прихований"
                ws.append_row(
                    [
                        booking.id,
                        datetime.now(KYIV_TZ).strftime("%d.%m.%Y %H:%M"),
                        _sanitize_cell(booking.full_name),
                        _sanitize_cell(booking.phone),
                        booking.age,
                        booking.tickets_count,
                        _sanitize_cell(booking.other_participants),
                        _sanitize_cell(booking.discount_info),
                        _sanitize_cell(booking.notes),
                        booking.amount,
                        mark,
                        _sanitize_cell(tg_nick),
                    ],
                    value_input_option="RAW",
                )

        await asyncio.to_thread(_sync_update_mark)
