from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from loguru import logger


def _user_tag(user) -> str:
    if not user:
        return "unknown"
    name = f"@{user.username}" if user.username else f"id={user.id}"
    return f"{user.id} {name}"


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        tag = _user_tag(user)

        if isinstance(event, Message):
            if event.text:
                logger.debug("MSG  | {} | {}", tag, event.text[:120])
            elif event.photo:
                logger.debug("MSG  | {} | [фото]", tag)
            else:
                logger.debug(
                    "MSG  | {} | [{}]", tag, event.content_type
                )
        elif isinstance(event, CallbackQuery):
            logger.debug("CALL | {} | {}", tag, event.data)

        try:
            return await handler(event, data)
        except Exception:
            logger.exception(
                "Необработанное исключение | user={}", tag
            )
            raise
