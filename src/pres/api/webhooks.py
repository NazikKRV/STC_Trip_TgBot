from fastapi import APIRouter, Form, HTTPException, Request
from src.config import settings
from src.inf.db.repositories import (
    PostgresTourRepository,
    PostgresBookingRepository,
    PostgresUserRepository,
    PostgresPromoCodeRepository,
)
from src.inf.sheets.google_sheets import GoogleSheetsService
from src.app.services import BookingService

webhook_router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])


@webhook_router.post("/liqpay")
async def liqpay_webhook(
    request: Request,
    data: str = Form(...),
    signature: str = Form(...),
):
    session_pool = request.app.state.session_pool
    payment_gateway = request.app.state.payment_gateway
    notifier = request.app.state.notifier

    sheets_service = GoogleSheetsService(
        credentials_path=settings.google_credentials_path,
        sheet_id=settings.google_sheet_id,
    )

    async with session_pool() as session:
        booking_service = BookingService(
            booking_repo=PostgresBookingRepository(session),
            tour_repo=PostgresTourRepository(session),
            payment_gateway=payment_gateway,
            notifier=notifier,
            user_repo=PostgresUserRepository(session),
            promo_repo=PostgresPromoCodeRepository(session),
            sheets_service=sheets_service,
        )
        success = await booking_service.process_payment_webhook(data, signature)
        if not success:
            raise HTTPException(status_code=400, detail="Invalid signature or booking")

    return {"status": "ok"}
