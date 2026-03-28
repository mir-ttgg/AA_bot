from aiogram.types import CallbackQuery
from aiogram import Router, F
from loguru import logger

from database.session import SessionLocal
from database.crud import (
    get_topics,
    get_lessons,
    get_questions,
    get_question_with_answers,
)
from keyboards.keyboards_admin import (
    menu_admin,
    topics_kb,
    lessons_kb,
    questions_kb,
    question_detail_kb,
)
from services import emoji

router = Router()


@router.callback_query(F.data == "noop")
async def noop_handler(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data == "main_menu")
async def main_menu_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "Выберите действие:",
        reply_markup=menu_admin()
    )


@router.callback_query(F.data.startswith("topics:"))
async def topics_handler(callback: CallbackQuery):
    page = int(callback.data.split(":")[1])
    async with SessionLocal() as session:
        topics = await get_topics(session)
    await callback.message.edit_text(
        f"{emoji.EMOJI_WHITE_1} <b>Темы:</b>",
        reply_markup=topics_kb(topics, page)
    )


@router.callback_query(F.data.startswith("lessons:"))
async def lessons_handler(callback: CallbackQuery):
    parts = callback.data.split(":")
    topic_id = int(parts[1])
    page = int(parts[2])
    async with SessionLocal() as session:
        lessons = await get_lessons(session, topic_id)
    await callback.message.edit_text(
        f"{emoji.EMOJI_WHITE_2} <b>Уроки:</b>",
        reply_markup=lessons_kb(topic_id, lessons, page)
    )


@router.callback_query(F.data.startswith("questions:"))
async def questions_handler(callback: CallbackQuery):
    parts = callback.data.split(":")
    lesson_id = int(parts[1])
    page = int(parts[2])
    topic_id = int(parts[3])
    async with SessionLocal() as session:
        questions = await get_questions(session, lesson_id)
    kb = questions_kb(lesson_id, topic_id, questions, page)
    if callback.message.photo:
        await callback.message.delete()
        await callback.message.answer(f"{emoji.EMOJI_WHITE_3} <b>Вопросы:</b>", reply_markup=kb)
    else:
        await callback.message.edit_text(f"{emoji.EMOJI_WHITE_3}  <b>Вопросы:</b>", reply_markup=kb)


@router.callback_query(F.data.startswith("question_detail:"))
async def question_detail_handler(callback: CallbackQuery):
    parts = callback.data.split(":")
    question_id = int(parts[1])
    lesson_id = int(parts[2])
    topic_id = int(parts[3])
    async with SessionLocal() as session:
        question = await get_question_with_answers(session, question_id)
    if not question:
        await callback.answer("Вопрос не найден", show_alert=True)
        return

    answers_text = ""
    for ans in question.answers:
        mark = "✅" if ans.is_correct else "❌"
        answers_text += f"\n{mark} {ans.text}"

    text = (
        f"{emoji.EMOJI_WHITE_3}  <b>Вопрос:</b>\n{question.text}"
        + (f"\n\n<b>Варианты ответов:</b>{answers_text}"
           if question.answers else "\n\n<i>Вариантов ответов пока нет</i>")
    )
    kb = question_detail_kb(
        question_id, lesson_id, topic_id, question.answers,
        has_comment=bool(question.comment),
        has_image=bool(question.image_file_id),
    )
    if question.image_file_id:
        try:
            await callback.message.delete()
        except Exception:
            pass
        try:
            await callback.message.answer_photo(
                photo=question.image_file_id,
                caption=text,
                reply_markup=kb,
            )
        except Exception:
            logger.warning(
                "Невалидный file_id для вопроса id={}: {}",
                question.id, question.image_file_id
            )
            await callback.message.answer(text, reply_markup=kb)
        return

    # Нет фото — редактируем или пересылаем
    if callback.message.photo:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb)
    else:
        await callback.message.edit_text(text, reply_markup=kb)
