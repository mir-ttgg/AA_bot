import logging
import sys
from datetime import datetime
from os import getenv
from pathlib import Path
from zoneinfo import ZoneInfo

from loguru import logger


# ── Перехват стандартного logging (aiogram, sqlalchemy и др.) ─────────────────

class _InterceptHandler(logging.Handler):
    """Перенаправляет записи stdlib logging в loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def _moscow_time() -> str:
    return datetime.now(ZoneInfo("Europe/Moscow")).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


LOG_FORMAT = (
    "<green>{extra[msk]}</green> | "
    "<level>{level:<8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
    "<level>{message}</level>"
)


def setup_logging() -> None:
    log_level = getenv("LOG_LEVEL", "INFO").upper()

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logger.remove()

    logger.configure(
        patcher=lambda r: r["extra"].update(msk=_moscow_time())
    )

    # Файл — всё начиная с DEBUG, ротация 10 МБ
    logger.add(
        log_dir / "bot.log",
        level="DEBUG",
        format=LOG_FORMAT,
        rotation="10 MB",
        retention="14 days",
        compression="zip",
        encoding="utf-8",
        enqueue=True,
    )

    # Консоль — по уровню из .env (по умолчанию INFO)
    logger.add(
        sys.stdout,
        level=log_level,
        format=LOG_FORMAT,
        colorize=True,
        enqueue=True,
    )

    # Подключаем stdlib logging → loguru
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)
    for noisy in ("aiogram", "asyncio", "sqlalchemy"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
