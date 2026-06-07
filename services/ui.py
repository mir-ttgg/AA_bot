"""Вспомогательные функции для работы с сообщениями Telegram."""

from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

CAPTION_LIMIT = 1024


async def safe_delete(message: Message) -> None:
    try:
        await message.delete()
    except Exception:
        pass


async def delete_by_id(bot, chat_id: int, message_id: int) -> None:
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass


async def clear_aux_photo(callback: CallbackQuery, state: FSMContext) -> None:
    """Удаляет ранее отправленное отдельным сообщением фото (если было)."""
    data = await state.get_data()
    aux = data.get("aux_photo_id")
    if aux:
        await delete_by_id(callback.bot, callback.message.chat.id, aux)
        await state.update_data(aux_photo_id=None)


async def reveal_over_photo(
    message: Message, captions: list[str], full_text: str, reply_markup
) -> int | None:
    """Показывает текст на существующем фото-сообщении.

    captions — варианты подписи по убыванию полноты; берём первый, что
    влезает в лимит, и редактируем подпись (фото + текст вместе).
    Если ни один не влезает (или Telegram отверг) — оставляем фото без
    клавиатуры и шлём full_text отдельным сообщением. Возвращает
    message_id фото-сообщения для последующей очистки (или None).
    """
    for caption in captions:
        if len(caption) <= CAPTION_LIMIT:
            try:
                await message.edit_caption(
                    caption=caption, reply_markup=reply_markup
                )
                return None
            except TelegramBadRequest:
                break
    try:
        await message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    await message.answer(full_text, reply_markup=reply_markup)
    return message.message_id


async def send_photo_or_split(
    message: Message, photo, text: str, reply_markup
) -> int | None:
    """Шлёт фото + текст. Если текст влезает в подпись — одним сообщением,
    иначе фото и текст отдельно. Возвращает message_id фото-сообщения,
    которое нужно удалить при переходе (или None)."""
    if len(text) <= CAPTION_LIMIT:
        try:
            await message.answer_photo(
                photo, caption=text, reply_markup=reply_markup
            )
            return None
        except TelegramBadRequest:
            pass
    photo_msg = await message.answer_photo(photo)
    await message.answer(text, reply_markup=reply_markup)
    return photo_msg.message_id


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
