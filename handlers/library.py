from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from loguru import logger

from database.session import SessionLocal
from database.crud import (
    get_topics_with_questions,
    get_questions_for_topic,
)
from keyboards.keyboards_user import (
    library_topics_kb,
    library_browse_kb,
    main_menu_kb,
)
from services.ui import show, safe_delete

router = Router()

_CAPTION_LIMIT = 1024


def _correct_answer_text(question) -> str:
    correct = [a.text for a in question.answers if a.is_correct]
    return ", ".join(correct) if correct else "—"


def _browse_text(
    question, index: int, total: int, reveal: bool, for_caption: bool
) -> str:
    header = f"<b>ЭКГ {index + 1}/{total}</b>"
    base = f"{header}\n\n{question.text}"

    if not reveal:
        if for_caption and len(base) > _CAPTION_LIMIT:
            return base[:_CAPTION_LIMIT - 1] + "…"
        return base

    answer = f"<b>Ответ:</b> {_correct_answer_text(question)}"
    comment = f"\n\n<i>{question.comment}</i>" if question.comment else ""
    full = f"{base}\n\n{answer}{comment}"
    if not for_caption or len(full) <= _CAPTION_LIMIT:
        return full
    # Для подписи к фото — без текста вопроса (ЭКГ и так на картинке)
    short = f"{header}\n\n{answer}{comment}"
    if len(short) <= _CAPTION_LIMIT:
        return short
    return short[:_CAPTION_LIMIT - 1] + "…"


async def _send_browse(message: Message, topic_id: int, index: int) -> None:
    """Свежим сообщением показывает ЭКГ темы с номером index (не раскрыто)."""
    async with SessionLocal() as session:
        questions = await get_questions_for_topic(session, topic_id)

    if not questions:
        await message.answer(
            "В этой теме пока нет ЭКГ.",
            reply_markup=library_topics_kb([], 0),
        )
        return

    index = max(0, min(index, len(questions) - 1))
    question = questions[index]
    total = len(questions)
    kb = library_browse_kb(topic_id, index, total, revealed=False)

    if question.image_file_id:
        caption = _browse_text(question, index, total, False, for_caption=True)
        try:
            await message.answer_photo(
                question.image_file_id, caption=caption, reply_markup=kb
            )
            return
        except Exception:
            logger.warning(
                "Невалидный file_id ЭКГ id={}", question.id
            )
    await message.answer(
        _browse_text(question, index, total, False, for_caption=False),
        reply_markup=kb,
    )


# ── Список тем библиотеки ─────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:library")
@router.callback_query(F.data.startswith("lib:topics:"))
async def lib_topics(callback: CallbackQuery):
    page = 0
    if callback.data.startswith("lib:topics:"):
        page = int(callback.data.split(":")[2])

    async with SessionLocal() as session:
        topics = await get_topics_with_questions(session)

    if not topics:
        await show(
            callback,
            "<b>Библиотека</b>\n\nЭКГ ещё не добавлены. Загляни позже!",
            reply_markup=main_menu_kb(),
        )
        await callback.answer()
        return

    await show(
        callback,
        "<b>Список всех примеров ЭКГ</b>\n\nВыбери тему:",
        reply_markup=library_topics_kb(topics, page),
    )
    await callback.answer()


# ── Открыть тему (первая ЭКГ) ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("lib:open:"))
async def lib_open(callback: CallbackQuery):
    topic_id = int(callback.data.split(":")[2])
    logger.info(
        "USER {} | Библиотека: открыта тема {}",
        callback.from_user.id, topic_id
    )
    await safe_delete(callback.message)
    await _send_browse(callback.message, topic_id, 0)
    await callback.answer()


# ── Навигация Дальше/Предыдущий ───────────────────────────────────────────────

@router.callback_query(F.data.startswith("lib:nav:"))
async def lib_nav(callback: CallbackQuery):
    parts = callback.data.split(":")
    topic_id = int(parts[2])
    index = int(parts[3])
    await safe_delete(callback.message)
    await _send_browse(callback.message, topic_id, index)
    await callback.answer()


# ── Показать ответ ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("lib:show:"))
async def lib_show(callback: CallbackQuery):
    parts = callback.data.split(":")
    topic_id = int(parts[2])
    index = int(parts[3])

    async with SessionLocal() as session:
        questions = await get_questions_for_topic(session, topic_id)

    if not questions:
        await callback.answer("ЭКГ не найдены", show_alert=True)
        return

    index = max(0, min(index, len(questions) - 1))
    question = questions[index]
    total = len(questions)
    kb = library_browse_kb(topic_id, index, total, revealed=True)

    msg = callback.message
    if msg.photo:
        await msg.edit_caption(
            caption=_browse_text(question, index, total, True, True),
            reply_markup=kb,
        )
    else:
        await msg.edit_text(
            _browse_text(question, index, total, True, False),
            reply_markup=kb,
        )
    await callback.answer()
