from fastapi import APIRouter, Form, HTTPException, Request
from src.inf.db.repositories import (
    PostgresTourRepository,
    PostgresBookingRepository,
)
from src.app.services import BookingService

webhook_router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])


@webhook_router.post("/liqpay")
async def liqpay_webhook(
    request: Request,
    data: str = Form(...),
    signature: str = Form(...),
):
    """Ендпоінт, на який ПриватБанк (LiqPay) автоматично надсилає статус оплати."""
    session_pool = request.app.state.session_pool
    payment_gateway = request.app.state.payment_gateway
    notifier = request.app.state.notifier

    async with session_pool() as session:
        booking_service = BookingService(
            booking_repo=PostgresBookingRepository(session),
            tour_repo=PostgresTourRepository(session),
            payment_gateway=payment_gateway,
            notifier=notifier,
        )
        success = await booking_service.process_payment_webhook(data, signature)
        if not success:
            raise HTTPException(status_code=400, detail="Invalid signature or booking")

    return {"status": "ok"}