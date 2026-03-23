import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

# Логирование инициализируется первым — до остальных импортов
from services.logger import setup_logging
setup_logging()

from loguru import logger  # noqa: E402

from config import BOT_TOKEN
from database.session import init_db
from middlewares.adminmiddlewares import AdminMiddleware
from middlewares.logging_middleware import LoggingMiddleware
from handlers import start, topics_lessons_questions
from handlers import admin_constructor, user_quiz

dp = Dispatcher(storage=MemoryStorage())
dp.include_routers(
    start.router,
    admin_constructor.router,
    topics_lessons_questions.router,
    user_quiz.router,
)
dp.update.middleware(LoggingMiddleware())
dp.update.middleware(AdminMiddleware())


async def main() -> None:
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    bot_info = await bot.get_me()
    logger.info(
        "Запуск бота | @{username} (id={id})",
        username=bot_info.username,
        id=bot_info.id,
    )

    try:
        await init_db()
        logger.info("БД инициализирована")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception:
        logger.exception("Критическая ошибка при запуске")
    finally:
        await bot.session.close()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main())
