import random

from aiogram import Router, F
from aiogram.types import CallbackQuery, InputMediaPhoto
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger

from database.session import SessionLocal
from database.crud import (
    get_lessons,
    get_lesson,
    get_questions,
    get_question_with_answers,
    get_topics,
    save_progress,
    get_random_questions_for_quiz,
)
from keyboards.keyboards_user import (
    user_topics_kb,
    user_lessons_kb,
    user_lesson_kb,
    quiz_question_kb,
    quiz_next_kb,
    random_quiz_count_kb,
    user_menu_kb,
)
from states import UserStates
from services import emoji

router = Router()


async def _safe_edit(callback: CallbackQuery, text: str, **kwargs):
    """edit_text или delete+answer, если сообщение содержит фото."""
    if callback.message.photo:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(text, **kwargs)
    else:
        await callback.message.edit_text(text, **kwargs)


def _pick_answers(answers: list) -> tuple[list, int]:
    """
    Выбирает варианты для вопроса в зависимости от числа правильных ответов:
      1 правильный → 4 варианта (1 верный + 3 неверных)
      2 правильных → 5 вариантов (2 верных + 3 неверных)
      3+ правильных → 6 вариантов (3 верных + 3 неверных)
    Возвращает (список вариантов, кол-во правильных).
    """
    correct_pool = [a for a in answers if a.is_correct]
    wrong_pool = [a for a in answers if not a.is_correct]

    n_correct = min(len(correct_pool), 3)
    if n_correct == 0:
        return [], 0

    n_wrong = 3  # всегда 3 неверных варианта
    chosen_correct = random.sample(correct_pool, n_correct)
    chosen_wrong = random.sample(wrong_pool, min(n_wrong, len(wrong_pool)))

    chosen = chosen_correct + chosen_wrong
    random.shuffle(chosen)
    return chosen, n_correct


# ── Назад к стартовому меню ───────────────────────────────────────────────────

@router.callback_query(F.data == "user:back_to_start")
async def back_to_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text = "Выберите действие:"
    if callback.message.photo:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(text, reply_markup=user_menu_kb())
    else:
        await callback.message.edit_text(text, reply_markup=user_menu_kb())


# ── Список тем ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("user:topics:"))
async def user_topics_handler(callback: CallbackQuery):
    page = int(callback.data.split(":")[2])
    async with SessionLocal() as session:
        topics = await get_topics(session)

    if not topics:
        await _safe_edit(callback, f"{emoji.EMOJI_WHITE_1} Темы ещё не добавлены. Загляни позже!")
        return

    await _safe_edit(
        callback,
        f"{emoji.EMOJI_WHITE_1} <b>Выберите тему:</b>",
        reply_markup=user_topics_kb(topics, page)
    )


# ── Список уроков ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("user:lessons:"))
async def user_lessons_handler(callback: CallbackQuery):
    parts = callback.data.split(":")
    topic_id = int(parts[2])
    page = int(parts[3])
    async with SessionLocal() as session:
        lessons = await get_lessons(session, topic_id)

    if not lessons:
        await callback.answer(
            "В этой теме пока нет уроков", show_alert=True
        )
        return

    await _safe_edit(
        callback,
        f"{emoji.EMOJI_WHITE_2} <b>Выберите урок:</b>",
        reply_markup=user_lessons_kb(topic_id, lessons, page)
    )


# ── Информация об уроке ───────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("user:lesson:"))
async def user_lesson_handler(callback: CallbackQuery):
    parts = callback.data.split(":")
    lesson_id = int(parts[2])
    topic_id = int(parts[3])
    async with SessionLocal() as session:
        lesson = await get_lesson(session, lesson_id)
        questions = await get_questions(session, lesson_id)

    if not lesson:
        await callback.answer("Урок не найден", show_alert=True)
        return

    question_count = len(questions)
    text = (
        f"{emoji.EMOJI_WHITE_2} <b>{lesson.title}</b>\n\n"
        f"Вопросов в тесте: <b>{question_count}</b>"
    )
    if question_count == 0:
        text += "\n\n<i>В этом уроке пока нет вопросов.</i>"

    await _safe_edit(
        callback,
        text,
        reply_markup=user_lesson_kb(lesson_id, topic_id, question_count)
    )


# ── Начать тест по уроку ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("user:start_quiz:"))
async def start_quiz(callback: CallbackQuery, state: FSMContext):
    lesson_id = int(callback.data.split(":")[2])
    async with SessionLocal() as session:
        questions = await get_questions(session, lesson_id)

    if not questions:
        await callback.answer("В уроке нет вопросов", show_alert=True)
        return

    question_ids = [q.id for q in questions]
    await state.set_state(UserStates.in_quiz)
    await state.update_data(
        question_ids=question_ids,
        current_index=0,
        correct_count=0,
        lesson_id=lesson_id,
        quiz_mode="lesson",
    )
    logger.info(
        "USER {} | Тест начат | lesson_id={}, вопросов={}",
        callback.from_user.id, lesson_id, len(question_ids)
    )
    await _show_question(
        callback, state, question_ids[0], 0, len(question_ids)
    )


# ── Случайный тест — меню выбора количества ───────────────────────────────────

@router.callback_query(F.data == "user:random_quiz_menu")
async def random_quiz_menu(callback: CallbackQuery):
    await _safe_edit(
        callback,
        "🎲 <b>Случайный тест</b>\n\n"
        "Вопросы берутся из всей базы в случайном порядке.\n"
        "Выберите количество вопросов:",
        reply_markup=random_quiz_count_kb()
    )


# ── Случайный тест — старт ────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("user:random_quiz:"))
async def start_random_quiz(callback: CallbackQuery, state: FSMContext):
    count = int(callback.data.split(":")[2])
    async with SessionLocal() as session:
        questions = await get_random_questions_for_quiz(session, count)

    if not questions:
        await callback.answer(
            "Недостаточно вопросов в базе для случайного теста.\n"
            "Сначала добавьте вопросы с вариантами ответов.",
            show_alert=True
        )
        return

    question_ids = [q.id for q in questions]
    await state.set_state(UserStates.in_quiz)
    await state.update_data(
        question_ids=question_ids,
        current_index=0,
        correct_count=0,
        lesson_id=None,
        quiz_mode="random",
    )
    logger.info(
        "USER {} | Случайный тест начат | вопросов={}",
        callback.from_user.id, len(question_ids)
    )
    await _show_question(
        callback, state, question_ids[0], 0, len(question_ids)
    )


# ── Показать вопрос ───────────────────────────────────────────────────────────

async def _show_question(
    callback: CallbackQuery,
    state: FSMContext,
    question_id: int,
    index: int,
    total: int,
):
    async with SessionLocal() as session:
        question = await get_question_with_answers(session, question_id)

    if not question:
        await _skip_question(callback, state, index, total)
        return

    display_answers, n_correct = _pick_answers(question.answers)

    if not display_answers:
        await _skip_question(callback, state, index, total)
        return

    data = await state.get_data()
    prev_has_photo = data.get("current_has_photo", False)
    next_has_photo = bool(question.image_file_id)

    await state.update_data(
        shown_answer_ids=[a.id for a in display_answers],
        n_correct=n_correct,
        selected_ids=[],
        current_has_photo=next_has_photo,
    )

    text = (
        f"❓ <b>Вопрос {index + 1}/{total}</b>\n\n"
        f"{question.text}"
    )
    kb = quiz_question_kb(display_answers, n_correct=n_correct, selected_ids=[])

    if next_has_photo and prev_has_photo:
        # Оба фото — редактируем медиа на месте
        await callback.message.edit_media(
            media=InputMediaPhoto(media=question.image_file_id, caption=text),
            reply_markup=kb,
        )
    elif not next_has_photo and not prev_has_photo:
        # Оба текст — просто редактируем текст на месте
        await callback.message.edit_text(text, reply_markup=kb)
    else:
        # Переключение между фото и текстом — удаляем и шлём новое
        try:
            await callback.message.delete()
        except Exception:
            pass
        if next_has_photo:
            await callback.message.answer_photo(
                photo=question.image_file_id,
                caption=text,
                reply_markup=kb,
            )
        else:
            await callback.message.answer(text, reply_markup=kb)


async def _skip_question(
    callback: CallbackQuery,
    state: FSMContext,
    index: int,
    total: int,
):
    """Пропустить вопрос без вариантов ответа."""
    data = await state.get_data()
    question_ids = data["question_ids"]
    next_index = index + 1
    if next_index < total:
        await state.update_data(current_index=next_index)
        await _show_question(
            callback, state,
            question_ids[next_index], next_index, total
        )
    else:
        await _show_result(callback, state)


# ── Обработка ответа ──────────────────────────────────────────────────────────

@router.callback_query(
    UserStates.in_quiz, F.data.startswith("user:answer:")
)
async def process_answer(callback: CallbackQuery, state: FSMContext):
    answer_id = int(callback.data.split(":")[2])
    data = await state.get_data()
    question_ids = data["question_ids"]
    current_index = data["current_index"]
    correct_count = data["correct_count"]
    question_id = question_ids[current_index]
    total = len(question_ids)

    async with SessionLocal() as session:
        question = await get_question_with_answers(session, question_id)

    # Находим выбранный и правильный среди показанных вариантов
    shown_ids = set(data.get("shown_answer_ids", []))
    shown = [a for a in question.answers if a.id in shown_ids]
    chosen = next((a for a in shown if a.id == answer_id), None)
    correct = next((a for a in shown if a.is_correct), None)
    is_correct = chosen is not None and chosen.is_correct

    if is_correct:
        correct_count += 1

    async with SessionLocal() as session:
        await save_progress(
            session,
            user_id=callback.from_user.id,
            question_id=question_id,
            chosen_answer_id=answer_id,
            is_correct=is_correct,
        )

    await state.update_data(correct_count=correct_count)
    logger.debug(
        "USER {} | Ответ | question_id={}, correct={}, score={}/{}",
        callback.from_user.id, question_id, is_correct,
        correct_count, total
    )

    is_last = (current_index + 1) >= total

    if is_correct:
        feedback = f"{emoji.EMOJI_YES} <b>Правильно!</b>"
    else:
        correct_text = correct.text if correct else "—"
        chosen_text = chosen.text if chosen else "—"
        feedback = (
            f"{emoji.EMOJI_NO} <b>Неправильно!</b>\n"
            f"Ваш ответ: {chosen_text}\n"
            f"Правильный ответ: <b>{correct_text}</b>"
        )

    comment_block = (
        f"\n\n💬 <i>{question.comment}</i>" if question.comment else ""
    )
    if callback.message.photo:
        _LIMIT = 1024
        full = (
            f"{emoji.EMOJI_WHITE_3} <b>Вопрос {current_index + 1}/{total}</b>\n\n"
            f"{question.text}\n\n"
            f"{feedback}{comment_block}"
        )
        short = f"{feedback}{comment_block}"
        if len(full) <= _LIMIT:
            caption = full
        elif len(short) <= _LIMIT:
            caption = short
        else:
            from config import ADMIN_IDS
            for admin_id in ADMIN_IDS:
                try:
                    await callback.bot.send_message(
                        chat_id=admin_id,
                        text=(
                            f"⚠️ <b>Ошибка вопроса #{question_id}</b>\n\n"
                            "Caption превышает 1024 символа даже без текста вопроса. "
                            "Сократите комментарий."
                        ),
                    )
                except Exception:
                    pass
            caption = short[:_LIMIT - 1] + "…"
        await callback.message.edit_caption(
            caption=caption,
            reply_markup=quiz_next_kb(is_last),
        )
    else:
        text = (
            f"{emoji.EMOJI_WHITE_3} <b>Вопрос {current_index + 1}/{total}</b>\n\n"
            f"{question.text}\n\n"
            f"{feedback}{comment_block}"
        )
        await callback.message.edit_text(
            text,
            reply_markup=quiz_next_kb(is_last)
        )


# ── Переключение варианта (множественный выбор) ───────────────────────────────

@router.callback_query(
    UserStates.in_quiz, F.data.startswith("user:toggle:")
)
async def toggle_answer(callback: CallbackQuery, state: FSMContext):
    answer_id = int(callback.data.split(":")[2])
    data = await state.get_data()
    selected_ids: list = list(data.get("selected_ids", []))

    if answer_id in selected_ids:
        selected_ids.remove(answer_id)
    else:
        selected_ids.append(answer_id)

    await state.update_data(selected_ids=selected_ids)

    shown_ids = data.get("shown_answer_ids", [])
    n_correct = data.get("n_correct", 1)
    question_id = data["question_ids"][data["current_index"]]

    async with SessionLocal() as session:
        question = await get_question_with_answers(session, question_id)

    order = {aid: i for i, aid in enumerate(shown_ids)}
    shown = sorted(
        [a for a in question.answers if a.id in set(shown_ids)],
        key=lambda a: order.get(a.id, 0),
    )
    kb = quiz_question_kb(shown, n_correct=n_correct, selected_ids=selected_ids)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


# ── Отправка ответов (множественный выбор) ────────────────────────────────────

@router.callback_query(
    UserStates.in_quiz, F.data == "user:submit_answers"
)
async def submit_answers(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_ids: list = data.get("selected_ids", [])

    if not selected_ids:
        await callback.answer("Выберите хотя бы один ответ!", show_alert=True)
        return

    question_ids = data["question_ids"]
    current_index = data["current_index"]
    correct_count = data["correct_count"]
    question_id = question_ids[current_index]
    total = len(question_ids)
    shown_ids = set(data.get("shown_answer_ids", []))

    async with SessionLocal() as session:
        question = await get_question_with_answers(session, question_id)

    shown = [a for a in question.answers if a.id in shown_ids]
    correct_shown = [a for a in shown if a.is_correct]
    correct_shown_ids = {a.id for a in correct_shown}
    is_correct = set(selected_ids) == correct_shown_ids

    if is_correct:
        correct_count += 1

    async with SessionLocal() as session:
        await save_progress(
            session,
            user_id=callback.from_user.id,
            question_id=question_id,
            chosen_answer_id=selected_ids[0] if selected_ids else None,
            is_correct=is_correct,
        )

    await state.update_data(correct_count=correct_count)
    logger.debug(
        "USER {} | Множ. ответ | question_id={}, correct={}, score={}/{}",
        callback.from_user.id, question_id, is_correct,
        correct_count, total
    )

    is_last = (current_index + 1) >= total

    if is_correct:
        feedback = f"{emoji.EMOJI_YES} <b>Правильно!</b>"
    else:
        correct_texts = ", ".join(
            f"<b>{a.text}</b>" for a in correct_shown
        )
        feedback = (
            f"{emoji.EMOJI_NO} <b>Неправильно!</b>\n"
            f"Правильные ответы: {correct_texts}"
        )

    comment_block = (
        f"\n\n💬 <i>{question.comment}</i>" if question.comment else ""
    )
    if callback.message.photo:
        _LIMIT = 1024
        full = (
            f"{emoji.EMOJI_WHITE_3} "
            f"<b>Вопрос {current_index + 1}/{total}</b>\n\n"
            f"{question.text}\n\n"
            f"{feedback}{comment_block}"
        )
        short = f"{feedback}{comment_block}"
        caption = (
            full if len(full) <= _LIMIT
            else short if len(short) <= _LIMIT
            else short[:_LIMIT - 1] + "…"
        )
        await callback.message.edit_caption(
            caption=caption, reply_markup=quiz_next_kb(is_last)
        )
    else:
        text = (
            f"{emoji.EMOJI_WHITE_3} "
            f"<b>Вопрос {current_index + 1}/{total}</b>\n\n"
            f"{question.text}\n\n"
            f"{feedback}{comment_block}"
        )
        await callback.message.edit_text(
            text, reply_markup=quiz_next_kb(is_last)
        )


# ── Следующий вопрос ──────────────────────────────────────────────────────────

@router.callback_query(
    UserStates.in_quiz, F.data == "user:next_question"
)
async def next_question(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    question_ids = data["question_ids"]
    next_index = data["current_index"] + 1
    await state.update_data(current_index=next_index)
    await _show_question(
        callback, state,
        question_ids[next_index], next_index, len(question_ids)
    )


# ── Результат ─────────────────────────────────────────────────────────────────

@router.callback_query(
    UserStates.in_quiz, F.data == "user:show_result"
)
async def show_result(callback: CallbackQuery, state: FSMContext):
    await _show_result(callback, state)


async def _show_result(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    total = len(data["question_ids"])
    correct = data["correct_count"]
    lesson_id = data.get("lesson_id")
    quiz_mode = data.get("quiz_mode", "lesson")
    await state.clear()

    pct = round(correct / total * 100) if total else 0
    logger.info(
        "USER {} | Тест завершён | режим={}, результат={}/{} ({}%)",
        callback.from_user.id, quiz_mode, correct, total, pct
    )

    if pct == 100:
        grade = "🏆 Отлично! Все ответы верные!"
    elif pct >= 70:
        grade = "👍 Хорошо! Продолжай в том же духе."
    elif pct >= 40:
        grade = "📚 Неплохо, но есть над чем поработать."
    else:
        grade = "💪 Не сдавайся — попробуй ещё раз!"

    text = (
        f"📊 <b>Результаты теста</b>\n\n"
        f"Правильных ответов: <b>{correct}/{total}</b> ({pct}%)\n\n"
        f"{grade}"
    )
    builder = InlineKeyboardBuilder()
    if quiz_mode == "random":
        builder.button(
            text="🔄 Ещё случайный тест",
            callback_data="user:random_quiz_menu"
        )
    elif lesson_id is not None:
        builder.button(
            text="🔄 Пройти ещё раз",
            callback_data=f"user:start_quiz:{lesson_id}"
        )
    builder.button(text="📚 К темам", callback_data="user:topics:0")
    builder.adjust(1)

    if callback.message.photo:
        await callback.message.edit_caption(
            caption=text, reply_markup=builder.as_markup()
        )
    else:
        await callback.message.edit_text(
            text, reply_markup=builder.as_markup()
        )
