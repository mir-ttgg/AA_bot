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


def _question_text(question, index: int, total: int) -> str:
    return f"<b>ЭКГ {index + 1}/{total}</b>\n\n{question.text}"


def _question_caption(question, index: int, total: int) -> str:
    """Подпись к фото (вопрос). Тег <b> закрыт в начале, хвост резать
    безопасно."""
    text = _question_text(question, index, total)
    if len(text) > _CAPTION_LIMIT:
        text = text[:_CAPTION_LIMIT - 1] + "…"
    return text


def _revealed_text(
    question, index: int, total: int, include_question: bool
) -> str:
    header = f"<b>ЭКГ {index + 1}/{total}</b>"
    answer = f"<b>Ответ:</b> {_correct_answer_text(question)}"
    comment = f"\n\n<i>{question.comment}</i>" if question.comment else ""
    if include_question:
        return f"{header}\n\n{question.text}\n\n{answer}{comment}"
    return f"{header}\n\n{answer}{comment}"


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
        try:
            await message.answer_photo(
                question.image_file_id,
                caption=_question_caption(question, index, total),
                reply_markup=kb,
            )
            return
        except Exception:
            logger.warning("Невалидный file_id ЭКГ id={}", question.id)
    await message.answer(
        _question_text(question, index, total), reply_markup=kb
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
    full = _revealed_text(question, index, total, include_question=True)

    msg = callback.message
    if msg.photo:
        short = _revealed_text(question, index, total, include_question=False)
        if len(full) <= _CAPTION_LIMIT:
            await msg.edit_caption(caption=full, reply_markup=kb)
        elif len(short) <= _CAPTION_LIMIT:
            await msg.edit_caption(caption=short, reply_markup=kb)
        else:
            # Разбор не влезает в подпись — отдаём отдельным текстом
            await safe_delete(msg)
            await msg.answer(full, reply_markup=kb)
    else:
        await msg.edit_text(full, reply_markup=kb)
    await callback.answer()
