import asyncio
import logging
import os
from contextlib import asynccontextmanager
from aiogram import Bot, Dispatcher
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeAllGroupChats,
)
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
import uvicorn

from src.config import settings
from src.inf.db.models import Base
from src.inf.db.fsm_storage import PostgresFSMStorage
from src.inf.db.repositories import (
    PostgresTourRepository,
    PostgresFaqRepository,
    PostgresPromoCodeRepository,
)
from src.inf.payments.privat_liqpay import PrivatLiqPayGateway
from src.inf.notifications.telegram_notifier import TelegramNotificationService
from src.app.services import TourService
from src.pres.bot.middlewares import DependencyInjectionMiddleware
from src.pres.bot.handlers import router as bot_router
from src.pres.api.webhooks import webhook_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO)

    engine = create_async_engine(settings.async_database_url, echo=False)
    session_pool = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        migrations = [
            "ALTER TABLE tours ADD COLUMN IF NOT EXISTS duration_days INTEGER DEFAULT 1",
            "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()",
            "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS notes TEXT DEFAULT 'немає'",
            "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS discount_info TEXT DEFAULT 'немає'",
            "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS username VARCHAR(100)",
        ]
        for sql in migrations:
            await conn.execute(text(sql))

    async with session_pool() as session:
        tour_service = TourService(
            tour_repo=PostgresTourRepository(session),
            faq_repo=PostgresFaqRepository(session),
            promo_repo=PostgresPromoCodeRepository(session),
        )
        await tour_service.seed_defaults_if_empty()

    bot = Bot(token=settings.bot_token)
    storage = PostgresFSMStorage(session_pool=session_pool)
    dp = Dispatcher(storage=storage)

    payment_gateway = PrivatLiqPayGateway(
        public_key=settings.liqpay_public_key,
        private_key=settings.liqpay_private_key,
        webhook_base_url=settings.webhook_base_url,
        sandbox=settings.liqpay_sandbox,
    )
    notifier = TelegramNotificationService(bot)

    app.state.session_pool = session_pool
    app.state.payment_gateway = payment_gateway
    app.state.notifier = notifier

    dp.update.middleware(
        DependencyInjectionMiddleware(
            session_pool=session_pool,
            payment_gateway=payment_gateway,
            notifier=notifier,
        )
    )
    dp.include_router(bot_router)

    try:
        await bot.set_my_commands(
            commands=[
                BotCommand(command="start", description="🏠 Головне меню (показати кнопки)"),
            ],
            scope=BotCommandScopeAllPrivateChats(),
        )
        await bot.set_my_commands(
            commands=[
                BotCommand(command="admin", description="⚙️ Панель управління турами та групами"),
                BotCommand(command="sync_tours", description="🔄 Синхронізувати таблицю (Тури, FAQ, Промо)"),
                BotCommand(command="send_chat_link", description="📨 Розіслати посилання на чат групі"),
                BotCommand(command="id", description="🆔 Показати ID цього чату"),
            ],
            scope=BotCommandScopeAllGroupChats(),
        )
    except Exception as e:
        logging.warning("Не вдалося встановити команди меню бота: %s", e)

    polling_task = asyncio.create_task(dp.start_polling(bot, handle_signals=False))
    logging.info("Бот STC TRIPS та FastAPI сервер успішно запущені!")

    yield

    polling_task.cancel()
    await bot.session.close()
    await engine.dispose()


app = FastAPI(title="STC TRIPS Bot & Payment Webhook API", lifespan=lifespan)
app.include_router(webhook_router)


@app.get("/")
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "STC TRIPS Bot"}


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("src.main:app", host="0.0.0.0", port=port, reload=False)
