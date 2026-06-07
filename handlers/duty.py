import random

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from loguru import logger

from database.session import SessionLocal
from database.crud import (
    get_random_questions_global,
    get_question_with_answers,
    save_progress,
    save_duty_session,
)
from keyboards.keyboards_user import (
    duty_count_kb,
    duty_question_kb,
    duty_next_kb,
    duty_exit_confirm_kb,
    duty_result_kb,
    main_menu_kb,
)
from states import UserStates
from services import emoji
from services.ui import show, safe_delete

router = Router()

_CAPTION_LIMIT = 1024


def _pick_answers(answers: list) -> tuple[list, int]:
    """Варианты для вопроса: до 3 верных + 3 неверных, перемешанные."""
    correct_pool = [a for a in answers if a.is_correct]
    wrong_pool = [a for a in answers if not a.is_correct]

    n_correct = min(len(correct_pool), 3)
    if n_correct == 0:
        return [], 0

    chosen_correct = random.sample(correct_pool, n_correct)
    chosen_wrong = random.sample(wrong_pool, min(3, len(wrong_pool)))
    chosen = chosen_correct + chosen_wrong
    random.shuffle(chosen)
    return chosen, n_correct


def _trim_caption(text: str) -> str:
    if len(text) <= _CAPTION_LIMIT:
        return text
    return text[:_CAPTION_LIMIT - 1] + "…"


# ── Меню «Количество пациентов» ───────────────────────────────────────────────

@router.callback_query(F.data == "menu:duty")
async def duty_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await show(
        callback,
        "<b>Дежурство</b>\n\nСколько пациентов (ЭКГ) хочешь разобрать "
        "за смену?",
        reply_markup=duty_count_kb(),
    )
    await callback.answer()


# ── Старт дежурства ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("duty:start:"))
async def duty_start(callback: CallbackQuery, state: FSMContext):
    count = int(callback.data.split(":")[2])
    async with SessionLocal() as session:
        questions = await get_random_questions_global(session, count)

    if not questions:
        await callback.answer(
            "Недостаточно ЭКГ для дежурства. Сначала нужно наполнить банк.",
            show_alert=True,
        )
        return

    question_ids = [q.id for q in questions]
    await state.set_state(UserStates.in_duty)
    await state.update_data(
        question_ids=question_ids,
        current_index=0,
        correct_count=0,
        scored_indices=[],
    )
    logger.info(
        "USER {} | Дежурство начато | ЭКГ={}",
        callback.from_user.id, len(question_ids)
    )
    await safe_delete(callback.message)
    await _send_question(callback.message, state, 0)
    await callback.answer()


# ── Показ вопроса ─────────────────────────────────────────────────────────────

async def _send_question(
    message: Message, state: FSMContext, index: int
) -> None:
    data = await state.get_data()
    question_ids = data["question_ids"]
    total = len(question_ids)

    async with SessionLocal() as session:
        question = await get_question_with_answers(session, question_ids[index])

    display_answers, n_correct = (
        _pick_answers(question.answers) if question else ([], 0)
    )
    if not display_answers:
        # битый вопрос — пропускаем
        if index + 1 < total:
            await _send_question(message, state, index + 1)
        else:
            await _finish(message, state)
        return

    await state.update_data(
        current_index=index,
        shown_answer_ids=[a.id for a in display_answers],
        n_correct=n_correct,
        selected_ids=[],
    )

    text = f"<b>Пациент {index + 1}/{total}</b>\n\n{question.text}"
    kb = duty_question_kb(display_answers, n_correct, [])

    if question.image_file_id:
        try:
            await message.answer_photo(
                question.image_file_id,
                caption=_trim_caption(text),
                reply_markup=kb,
            )
            return
        except Exception:
            logger.warning("Невалидный file_id ЭКГ id={}", question.id)
    await message.answer(text, reply_markup=kb)


async def _render_feedback(
    callback: CallbackQuery, state: FSMContext,
    question, is_correct: bool, correct_texts: list[str],
) -> None:
    data = await state.get_data()
    index = data["current_index"]
    total = len(data["question_ids"])
    is_last = (index + 1) >= total

    if is_correct:
        feedback = "<b>Правильно!</b>"
    else:
        joined = ", ".join(f"<b>{t}</b>" for t in correct_texts) or "—"
        feedback = f"<b>Неправильно!</b>\nПравильный ответ: {joined}"

    comment = f"\n\n<i>{question.comment}</i>" if question.comment else ""
    body = (
        f"<b>Пациент {index + 1}/{total}</b>\n\n"
        f"{question.text}\n\n{feedback}{comment}"
    )
    kb = duty_next_kb(is_last)
    msg = callback.message
    if msg.photo:
        await msg.edit_caption(caption=_trim_caption(body), reply_markup=kb)
    else:
        await msg.edit_text(body, reply_markup=kb)


async def _score(
    state: FSMContext, user_id: int, question_id: int,
    chosen_id: int | None, is_correct: bool,
) -> None:
    """Учитывает ответ один раз на вопрос (идемпотентно)."""
    data = await state.get_data()
    index = data["current_index"]
    scored = list(data.get("scored_indices", []))
    if index in scored:
        return
    scored.append(index)
    correct_count = data.get("correct_count", 0) + (1 if is_correct else 0)
    async with SessionLocal() as session:
        await save_progress(
            session, user_id=user_id, question_id=question_id,
            chosen_answer_id=chosen_id, is_correct=is_correct,
        )
    await state.update_data(correct_count=correct_count, scored_indices=scored)


# ── Ответ (один правильный) ───────────────────────────────────────────────────

@router.callback_query(UserStates.in_duty, F.data.startswith("duty:answer:"))
async def duty_answer(callback: CallbackQuery, state: FSMContext):
    answer_id = int(callback.data.split(":")[2])
    data = await state.get_data()
    question_id = data["question_ids"][data["current_index"]]
    shown_ids = set(data.get("shown_answer_ids", []))

    async with SessionLocal() as session:
        question = await get_question_with_answers(session, question_id)

    shown = [a for a in question.answers if a.id in shown_ids]
    chosen = next((a for a in shown if a.id == answer_id), None)
    correct = next((a for a in shown if a.is_correct), None)
    is_correct = chosen is not None and chosen.is_correct

    await _score(
        state, callback.from_user.id, question_id, answer_id, is_correct
    )
    await _render_feedback(
        callback, state, question, is_correct,
        [correct.text] if correct else [],
    )
    await callback.answer()


# ── Множественный выбор ───────────────────────────────────────────────────────

@router.callback_query(UserStates.in_duty, F.data.startswith("duty:toggle:"))
async def duty_toggle(callback: CallbackQuery, state: FSMContext):
    answer_id = int(callback.data.split(":")[2])
    data = await state.get_data()
    selected_ids = list(data.get("selected_ids", []))
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
    kb = duty_question_kb(shown, n_correct, selected_ids)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@router.callback_query(UserStates.in_duty, F.data == "duty:submit")
async def duty_submit(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_ids = data.get("selected_ids", [])
    if not selected_ids:
        await callback.answer("Выбери хотя бы один ответ!", show_alert=True)
        return

    question_id = data["question_ids"][data["current_index"]]
    shown_ids = set(data.get("shown_answer_ids", []))
    async with SessionLocal() as session:
        question = await get_question_with_answers(session, question_id)

    shown = [a for a in question.answers if a.id in shown_ids]
    correct_shown = [a for a in shown if a.is_correct]
    is_correct = set(selected_ids) == {a.id for a in correct_shown}

    await _score(
        state, callback.from_user.id, question_id,
        selected_ids[0] if selected_ids else None, is_correct,
    )
    await _render_feedback(
        callback, state, question, is_correct,
        [a.text for a in correct_shown],
    )
    await callback.answer()


# ── Следующий пациент ─────────────────────────────────────────────────────────

@router.callback_query(UserStates.in_duty, F.data == "duty:next")
async def duty_next(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    next_index = data["current_index"] + 1
    await safe_delete(callback.message)
    await _send_question(callback.message, state, next_index)
    await callback.answer()


# ── Завершение / результат ────────────────────────────────────────────────────

@router.callback_query(UserStates.in_duty, F.data == "duty:result")
async def duty_result(callback: CallbackQuery, state: FSMContext):
    await _finish(callback.message, state, user_id=callback.from_user.id)
    await callback.answer()


async def _finish(
    message: Message, state: FSMContext, user_id: int | None = None
) -> None:
    data = await state.get_data()
    total = len(data.get("question_ids", []))
    correct = data.get("correct_count", 0)
    uid = user_id if user_id is not None else message.chat.id
    await state.clear()

    pct = round(correct / total * 100) if total else 0
    async with SessionLocal() as session:
        await save_duty_session(session, uid, total, correct)
    logger.info(
        "USER {} | Дежурство завершено | {}/{} ({}%)",
        uid, correct, total, pct
    )

    if pct == 100:
        grade = "Блестящая смена — ни одной ошибки!"
    elif pct >= 80:
        grade = "Отличная работа, так держать!"
    elif pct >= 60:
        grade = "Неплохо, но есть над чем поработать."
    else:
        grade = (
            "Сложная смена — потренируйся ещё, и результат вырастет! "
            f"{emoji.EMPJI_SIL}"
        )

    text = (
        "<b>Дежурство завершено</b>\n\n"
        f"Разобрано ЭКГ: <b>{total}</b>\n"
        f"Правильных ответов: <b>{correct}</b>\n"
        f"Точность: <b>{pct}%</b>\n\n{grade}"
    )
    if message.photo:
        await safe_delete(message)
        await message.answer(text, reply_markup=duty_result_kb())
    else:
        try:
            await message.edit_text(text, reply_markup=duty_result_kb())
        except Exception:
            await message.answer(text, reply_markup=duty_result_kb())


# ── Выход с подтверждением ────────────────────────────────────────────────────

@router.callback_query(UserStates.in_duty, F.data == "duty:exit")
async def duty_exit(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    correct = data.get("correct_count", 0)
    answered = len(data.get("scored_indices", []))
    text = (
        f"<b>Текущий результат: {correct}/{answered}</b>\n\n"
        "Вы уверены, что хотите выйти? Дежурство не будет засчитано "
        "в рейтинг."
    )
    msg = callback.message
    if msg.photo:
        await msg.edit_caption(
            caption=text, reply_markup=duty_exit_confirm_kb()
        )
    else:
        await msg.edit_text(text, reply_markup=duty_exit_confirm_kb())
    await callback.answer()


@router.callback_query(UserStates.in_duty, F.data == "duty:exit_cancel")
async def duty_exit_cancel(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    index = data.get("current_index", 0)
    await safe_delete(callback.message)
    await _send_question(callback.message, state, index)
    await callback.answer()


@router.callback_query(UserStates.in_duty, F.data == "duty:exit_confirm")
async def duty_exit_confirm(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    logger.info("USER {} | Дежурство прервано", callback.from_user.id)
    await show(
        callback,
        "<b>Главное меню</b>\n\nВыбери режим:",
        reply_markup=main_menu_kb(),
    )
    await callback.answer()
