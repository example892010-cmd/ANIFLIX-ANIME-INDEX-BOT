from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from app.config import Settings
from app.database.repository import Database
from app.handlers.router import build_router

async def run() -> None:
    settings = Settings.from_env()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    db = Database(settings.database_path)
    await db.connect()
    bot = Bot(settings.bot_token)
    dp = Dispatcher(); dp.include_router(build_router(db, settings))
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close(); await db.close()

if __name__ == '__main__':
    try: asyncio.run(run())
    except (KeyboardInterrupt, SystemExit): pass
