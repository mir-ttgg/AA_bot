"""Вспомогательные функции для работы с сообщениями Telegram."""

from aiogram.types import Message, CallbackQuery


async def safe_delete(message: Message) -> None:
    try:
        await message.delete()
    except Exception:
        pass


async def show(
    callback: CallbackQuery, text: str, reply_markup=None
) -> None:
    """Показать текстовый экран на месте текущего сообщения.

    Если текущее сообщение — фото (нельзя превратить в текст редактированием),
    удаляем его и шлём новое. Иначе редактируем текст.
    """
    msg = callback.message
    if msg.photo or msg.caption is not None:
        await safe_delete(msg)
        await msg.answer(text, reply_markup=reply_markup)
    else:
        try:
            await msg.edit_text(text, reply_markup=reply_markup)
        except Exception:
            await msg.answer(text, reply_markup=reply_markup)
