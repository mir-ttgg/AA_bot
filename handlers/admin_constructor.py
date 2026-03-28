from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from loguru import logger

from database.session import SessionLocal
from database.crud import (
    create_topic, get_topics, get_topic,
    create_lesson, get_lessons, get_lesson,
    create_question, get_questions, get_question,
    create_answer, get_answer, update_answer, delete_answer,
    get_question_with_answers,
    delete_topic, delete_lesson, delete_question,
    update_question_comment, update_question_image,
)
from keyboards.keyboards_admin import (
    topics_kb,
    lessons_kb,
    questions_kb,
    question_detail_kb,
    answer_actions_kb,
    cancel_kb,
    skip_image_kb,
    edit_image_kb,
    skip_comment_kb,
    answer_correct_kb,
    confirm_delete_kb,
)
from states import AdminStates

router = Router()


# ── Отмена ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:cancel")
async def admin_cancel(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    back_to = data.get("back_to", "topics")

    async with SessionLocal() as session:
        if back_to == "topics":
            topics = await get_topics(session)
            await callback.message.edit_text(
                "📚 <b>Темы:</b>",
                reply_markup=topics_kb(topics)
            )
        elif back_to == "lessons":
            topic_id = data["topic_id"]
            lessons = await get_lessons(session, topic_id)
            await callback.message.edit_text(
                "📖 <b>Уроки:</b>",
                reply_markup=lessons_kb(topic_id, lessons)
            )
        elif back_to == "questions":
            lesson_id = data["lesson_id"]
            topic_id = data["topic_id"]
            questions = await get_questions(session, lesson_id)
            await callback.message.edit_text(
                "❓ <b>Вопросы:</b>",
                reply_markup=questions_kb(lesson_id, topic_id, questions)
            )
        elif back_to == "question_detail":
            question_id = data["question_id"]
            lesson_id = data["lesson_id"]
            topic_id = data["topic_id"]
            question = await get_question_with_answers(
                session, question_id
            )
            if question:
                answers_text = "".join(
                    f"\n{'✅' if a.is_correct else '❌'} {a.text}"
                    for a in question.answers
                )
                text = (
                    f"❓ <b>Вопрос:</b>\n{question.text}"
                    + (f"\n\n<b>Варианты:</b>{answers_text}"
                       if question.answers
                       else "\n\n<i>Вариантов нет</i>")
                )
                kb = question_detail_kb(
                    question_id, lesson_id, topic_id,
                    question.answers,
                    has_comment=bool(question.comment),
                    has_image=bool(question.image_file_id),
                )
                if callback.message.photo:
                    await callback.message.edit_caption(
                        caption=text, reply_markup=kb
                    )
                else:
                    await callback.message.edit_text(text, reply_markup=kb)
        elif back_to == "answer_detail":
            answer_id = data["answer_id"]
            question_id = data["question_id"]
            lesson_id = data["lesson_id"]
            topic_id = data["topic_id"]
            is_photo = data.get("is_photo_message", False)
            answer = await get_answer(session, answer_id)
            if answer:
                text = _answer_detail_text(answer)
                kb = answer_actions_kb(
                    answer_id, question_id, lesson_id, topic_id,
                    answer.is_correct
                )
                if is_photo:
                    await callback.message.edit_caption(
                        caption=text, reply_markup=kb
                    )
                else:
                    await callback.message.edit_text(text, reply_markup=kb)


# ── Создать тему ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "create:topic")
async def start_create_topic(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_topic_title)
    await state.update_data(
        back_to="topics",
        message_id=callback.message.message_id
    )
    await callback.message.edit_text(
        "✏️ Введите название новой темы:",
        reply_markup=cancel_kb()
    )


@router.message(AdminStates.waiting_topic_title, F.text)
async def process_topic_title(
    message: Message, state: FSMContext, bot: Bot
):
    data = await state.get_data()
    msg_id = data["message_id"]
    title = message.text.strip()
    await state.clear()

    await message.delete()
    async with SessionLocal() as session:
        await create_topic(session, title)
        topics = await get_topics(session)
    logger.info("ADMIN {} | Создана тема «{}»", message.from_user.id, title)

    await bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=msg_id,
        text="📚 <b>Темы:</b>",
        reply_markup=topics_kb(topics)
    )


# ── Создать урок ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("create:lesson:"))
async def start_create_lesson(
    callback: CallbackQuery, state: FSMContext
):
    topic_id = int(callback.data.split(":")[2])
    await state.set_state(AdminStates.waiting_lesson_title)
    await state.update_data(
        back_to="lessons",
        topic_id=topic_id,
        message_id=callback.message.message_id
    )
    await callback.message.edit_text(
        "✏️ Введите название нового урока:",
        reply_markup=cancel_kb()
    )


@router.message(AdminStates.waiting_lesson_title, F.text)
async def process_lesson_title(
    message: Message, state: FSMContext, bot: Bot
):
    data = await state.get_data()
    msg_id = data["message_id"]
    topic_id = data["topic_id"]
    title = message.text.strip()
    await state.clear()

    await message.delete()
    async with SessionLocal() as session:
        await create_lesson(session, title, topic_id)
        lessons = await get_lessons(session, topic_id)
    logger.info(
        "ADMIN {} | Создан урок «{}» (topic_id={})",
        message.from_user.id, title, topic_id
    )

    await bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=msg_id,
        text="📖 <b>Уроки:</b>",
        reply_markup=lessons_kb(topic_id, lessons)
    )


# ── Создать вопрос ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("create:question:"))
async def start_create_question(
    callback: CallbackQuery, state: FSMContext
):
    parts = callback.data.split(":")
    lesson_id = int(parts[2])
    topic_id = int(parts[3])
    await state.set_state(AdminStates.waiting_question_text)
    await state.update_data(
        back_to="questions",
        lesson_id=lesson_id,
        topic_id=topic_id,
        message_id=callback.message.message_id
    )
    await callback.message.edit_text(
        "✏️ Введите текст вопроса:",
        reply_markup=cancel_kb()
    )


@router.message(AdminStates.waiting_question_text, F.text)
async def process_question_text(
    message: Message, state: FSMContext, bot: Bot
):
    data = await state.get_data()
    msg_id = data["message_id"]
    q_text = message.text.strip()
    await message.delete()
    await state.set_state(AdminStates.waiting_question_image)
    await state.update_data(question_text=q_text)

    await bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=msg_id,
        text=(
            f"🖼 Отправьте изображение к вопросу:\n\n"
            f"«<b>{q_text}</b>»\n\n"
            f"<i>Или нажмите «Пропустить», чтобы оставить без фото.</i>"
        ),
        reply_markup=skip_image_kb()
    )


async def _ask_for_comment(
    chat_id: int,
    msg_id: int,
    bot: Bot,
    state: FSMContext,
    image_file_id: str | None,
):
    """После загрузки фото (или пропуска) — запрашиваем комментарий."""
    await state.update_data(image_file_id=image_file_id)
    await state.set_state(AdminStates.waiting_question_comment)
    prompt = (
        "💬 Введите комментарий к вопросу:\n\n"
        "<i>Он будет показан пользователю после ответа.</i>"
    )
    if image_file_id:
        await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        sent = await bot.send_photo(
            chat_id=chat_id,
            photo=image_file_id,
            caption=prompt,
            reply_markup=skip_comment_kb(),
        )
        await state.update_data(message_id=sent.message_id)
    else:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=prompt,
            reply_markup=skip_comment_kb(),
        )


async def _actually_create_question(
    chat_id: int,
    msg_id: int,
    bot: Bot,
    state: FSMContext,
    comment: str | None,
):
    data = await state.get_data()
    lesson_id = data["lesson_id"]
    topic_id = data["topic_id"]
    q_text = data["question_text"]
    image_file_id = data.get("image_file_id")
    await state.clear()

    async with SessionLocal() as session:
        question = await create_question(
            session, q_text, lesson_id, image_file_id, comment
        )
        question = await get_question_with_answers(session, question.id)
    logger.info(
        "ADMIN | Создан вопрос id={} (lesson_id={}, фото={}, комментарий={})",
        question.id, lesson_id, bool(image_file_id), bool(comment)
    )

    text = (
        f"❓ <b>Вопрос создан!</b>\n\n{question.text}\n\n"
        "<i>Вариантов ответов пока нет. Добавьте их ниже.</i>"
    )
    kb = question_detail_kb(
        question.id, lesson_id, topic_id,
        question.answers,
        has_comment=bool(question.comment),
        has_image=bool(question.image_file_id),
    )

    if image_file_id:
        await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        await bot.send_photo(
            chat_id=chat_id,
            photo=image_file_id,
            caption=text,
            reply_markup=kb,
        )
    else:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=text,
            reply_markup=kb,
        )


@router.message(AdminStates.waiting_question_image, F.photo)
async def process_question_image(
    message: Message, state: FSMContext, bot: Bot
):
    data = await state.get_data()
    msg_id = data["message_id"]
    file_id = message.photo[-1].file_id
    await message.delete()
    await _ask_for_comment(message.chat.id, msg_id, bot, state, file_id)


@router.callback_query(
    AdminStates.waiting_question_image, F.data == "admin:skip_image"
)
async def skip_question_image(
    callback: CallbackQuery, state: FSMContext, bot: Bot
):
    data = await state.get_data()
    msg_id = data["message_id"]
    await _ask_for_comment(
        callback.message.chat.id, msg_id, bot, state, None
    )


@router.message(AdminStates.waiting_question_comment, F.text)
async def process_question_comment(
    message: Message, state: FSMContext, bot: Bot
):
    data = await state.get_data()
    msg_id = data["message_id"]
    comment = message.text.strip()
    await message.delete()
    await _actually_create_question(
        message.chat.id, msg_id, bot, state, comment
    )


@router.callback_query(
    AdminStates.waiting_question_comment,
    F.data == "admin:skip_comment"
)
async def skip_question_comment(
    callback: CallbackQuery, state: FSMContext, bot: Bot
):
    data = await state.get_data()
    msg_id = data["message_id"]
    await _actually_create_question(
        callback.message.chat.id, msg_id, bot, state, None
    )


# ── Создать вариант ответа ────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("create:answer:"))
async def start_create_answer(
    callback: CallbackQuery, state: FSMContext
):
    parts = callback.data.split(":")
    question_id = int(parts[2])
    lesson_id = int(parts[3])
    topic_id = int(parts[4])
    is_photo = bool(callback.message.photo)
    await state.set_state(AdminStates.waiting_answer_text)
    await state.update_data(
        back_to="question_detail",
        question_id=question_id,
        lesson_id=lesson_id,
        topic_id=topic_id,
        message_id=callback.message.message_id,
        is_photo_message=is_photo,
    )
    if is_photo:
        await callback.message.edit_caption(
            caption="✏️ Введите текст варианта ответа:",
            reply_markup=cancel_kb()
        )
    else:
        await callback.message.edit_text(
            "✏️ Введите текст варианта ответа:",
            reply_markup=cancel_kb()
        )


@router.message(AdminStates.waiting_answer_text, F.text)
async def process_answer_text(
    message: Message, state: FSMContext, bot: Bot
):
    data = await state.get_data()
    msg_id = data["message_id"]
    is_photo = data.get("is_photo_message", False)
    answer_text = message.text.strip()
    await message.delete()
    await state.set_state(AdminStates.waiting_answer_correct)
    await state.update_data(answer_text=answer_text)

    prompt = (
        f"✏️ Вариант: «<b>{answer_text}</b>»\n\n"
        "Это правильный ответ?"
    )
    if is_photo:
        await bot.edit_message_caption(
            chat_id=message.chat.id,
            message_id=msg_id,
            caption=prompt,
            reply_markup=answer_correct_kb()
        )
    else:
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=msg_id,
            text=prompt,
            reply_markup=answer_correct_kb()
        )


@router.callback_query(
    AdminStates.waiting_answer_correct,
    F.data.startswith("admin:answer_correct:")
)
async def process_answer_correct(
    callback: CallbackQuery, state: FSMContext
):
    is_correct = callback.data.endswith(":yes")
    data = await state.get_data()
    question_id = data["question_id"]
    lesson_id = data["lesson_id"]
    topic_id = data["topic_id"]
    answer_text = data["answer_text"]
    await state.clear()

    async with SessionLocal() as session:
        await create_answer(session, question_id, answer_text, is_correct)
        question = await get_question_with_answers(session, question_id)
    logger.info(
        "ADMIN {} | Добавлен вариант ответа (question_id={}, correct={})",
        callback.from_user.id, question_id, is_correct
    )

    answers_text = "".join(
        f"\n{'✅' if a.is_correct else '❌'} {a.text}"
        for a in question.answers
    )
    text = (
        f"❓ <b>Вопрос:</b>\n{question.text}"
        + (f"\n\n<b>Варианты:</b>{answers_text}"
           if question.answers else "\n\n<i>Вариантов нет</i>")
    )
    kb = question_detail_kb(
        question_id, lesson_id, topic_id,
        question.answers,
        has_comment=bool(question.comment),
        has_image=bool(question.image_file_id),
    )
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb)
    else:
        await callback.message.edit_text(text, reply_markup=kb)


# ── Удалить тему ──────────────────────────────────────────────────────────────

# ── Подтверждение удаления темы ───────────────────────────────────────────────

@router.callback_query(F.data.startswith("delete:topic:"))
async def confirm_delete_topic(callback: CallbackQuery):
    topic_id = int(callback.data.split(":")[2])
    async with SessionLocal() as session:
        topic = await get_topic(session, topic_id)
    if not topic:
        await callback.answer("Тема не найдена", show_alert=True)
        return
    await callback.message.edit_text(
        f"🗑 Удалить тему «<b>{topic.title}</b>»?\n\n"
        "<i>Все уроки и вопросы внутри будут удалены.</i>",
        reply_markup=confirm_delete_kb(
            confirm_cb=f"confirm:delete:topic:{topic_id}",
            cancel_cb=f"lessons:{topic_id}:0",
        )
    )


@router.callback_query(F.data.startswith("confirm:delete:topic:"))
async def do_delete_topic(callback: CallbackQuery):
    topic_id = int(callback.data.split(":")[3])
    async with SessionLocal() as session:
        await delete_topic(session, topic_id)
        topics = await get_topics(session)
    logger.warning(
        "ADMIN {} | Удалена тема id={}", callback.from_user.id, topic_id
    )
    await callback.message.edit_text(
        "📚 <b>Темы:</b>",
        reply_markup=topics_kb(topics)
    )
    await callback.answer("Тема удалена")


# ── Подтверждение удаления урока ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("delete:lesson:"))
async def confirm_delete_lesson(callback: CallbackQuery):
    parts = callback.data.split(":")
    lesson_id = int(parts[2])
    topic_id = int(parts[3])
    async with SessionLocal() as session:
        lesson = await get_lesson(session, lesson_id)
    if not lesson:
        await callback.answer("Урок не найден", show_alert=True)
        return
    await callback.message.edit_text(
        f"🗑 Удалить урок «<b>{lesson.title}</b>»?\n\n"
        "<i>Все вопросы и ответы внутри будут удалены.</i>",
        reply_markup=confirm_delete_kb(
            confirm_cb=f"confirm:delete:lesson:{lesson_id}:{topic_id}",
            cancel_cb=f"questions:{lesson_id}:0:{topic_id}",
        )
    )


@router.callback_query(F.data.startswith("confirm:delete:lesson:"))
async def do_delete_lesson(callback: CallbackQuery):
    parts = callback.data.split(":")
    lesson_id = int(parts[3])
    topic_id = int(parts[4])
    async with SessionLocal() as session:
        await delete_lesson(session, lesson_id)
        lessons = await get_lessons(session, topic_id)
    logger.warning(
        "ADMIN {} | Удалён урок id={}", callback.from_user.id, lesson_id
    )
    await callback.message.edit_text(
        "📖 <b>Уроки:</b>",
        reply_markup=lessons_kb(topic_id, lessons)
    )
    await callback.answer("Урок удалён")


# ── Подтверждение удаления вопроса ────────────────────────────────────────────

@router.callback_query(F.data.startswith("delete:question:"))
async def confirm_delete_question(callback: CallbackQuery):
    parts = callback.data.split(":")
    question_id = int(parts[2])
    lesson_id = int(parts[3])
    topic_id = int(parts[4])
    async with SessionLocal() as session:
        question = await get_question(session, question_id)
    if not question:
        await callback.answer("Вопрос не найден", show_alert=True)
        return
    preview = (
        question.text[:80] + "…"
        if len(question.text) > 80
        else question.text
    )
    text = (
        f"🗑 Удалить вопрос?\n\n«<b>{preview}</b>»\n\n"
        "<i>Все варианты ответов будут удалены.</i>"
    )
    kb = confirm_delete_kb(
        confirm_cb=(
            f"confirm:delete:question:"
            f"{question_id}:{lesson_id}:{topic_id}"
        ),
        cancel_cb=(
            f"question_detail:{question_id}:{lesson_id}:{topic_id}"
        ),
    )
    if callback.message.text:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("confirm:delete:question:"))
async def do_delete_question(callback: CallbackQuery):
    parts = callback.data.split(":")
    question_id = int(parts[3])
    lesson_id = int(parts[4])
    topic_id = int(parts[5])
    async with SessionLocal() as session:
        await delete_question(session, question_id)
        questions = await get_questions(session, lesson_id)
    logger.warning(
        "ADMIN {} | Удалён вопрос id={}", callback.from_user.id, question_id
    )
    await callback.message.edit_text(
        "❓ <b>Вопросы:</b>",
        reply_markup=questions_kb(lesson_id, topic_id, questions)
    )
    await callback.answer("Вопрос удалён")


# ── Детали варианта ответа ────────────────────────────────────────────────────

def _answer_detail_text(answer) -> str:
    mark = "✅ Правильный" if answer.is_correct else "❌ Неправильный"
    return f"💬 <b>Вариант ответа</b>\n\n{answer.text}\n\n<i>{mark}</i>"


@router.callback_query(F.data.startswith("answer_detail:"))
async def answer_detail_handler(callback: CallbackQuery):
    parts = callback.data.split(":")
    answer_id = int(parts[1])
    question_id = int(parts[2])
    lesson_id = int(parts[3])
    topic_id = int(parts[4])
    async with SessionLocal() as session:
        answer = await get_answer(session, answer_id)
    if not answer:
        await callback.answer("Вариант не найден", show_alert=True)
        return
    if callback.message.photo:
        await callback.message.edit_caption(
            caption=_answer_detail_text(answer),
            reply_markup=answer_actions_kb(
                answer_id, question_id, lesson_id, topic_id, answer.is_correct
            )
        )
    else:
        await callback.message.edit_text(
            _answer_detail_text(answer),
            reply_markup=answer_actions_kb(
                answer_id, question_id, lesson_id, topic_id, answer.is_correct
            )
        )


# ── Переключить правильность ответа ──────────────────────────────────────────

@router.callback_query(F.data.startswith("toggle:answer:"))
async def toggle_answer_correct(callback: CallbackQuery):
    parts = callback.data.split(":")
    answer_id = int(parts[2])
    question_id = int(parts[3])
    lesson_id = int(parts[4])
    topic_id = int(parts[5])
    async with SessionLocal() as session:
        answer = await get_answer(session, answer_id)
        if not answer:
            await callback.answer("Вариант не найден", show_alert=True)
            return
        await update_answer(session, answer_id, is_correct=not answer.is_correct)
        answer = await get_answer(session, answer_id)
    logger.info(
        "ADMIN {} | Изменён статус ответа id={} → is_correct={}",
        callback.from_user.id, answer_id, answer.is_correct
    )
    if callback.message.photo:
        await callback.message.edit_caption(
            caption=_answer_detail_text(answer),
            reply_markup=answer_actions_kb(
                answer_id, question_id, lesson_id, topic_id, answer.is_correct
            )
        )
    else:
        await callback.message.edit_text(
            _answer_detail_text(answer),
            reply_markup=answer_actions_kb(
                answer_id, question_id, lesson_id, topic_id, answer.is_correct
            )
        )


# ── Редактировать текст ответа ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("edit:answer:"))
async def start_edit_answer(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    answer_id = int(parts[2])
    question_id = int(parts[3])
    lesson_id = int(parts[4])
    topic_id = int(parts[5])
    is_photo = bool(callback.message.photo)
    await state.set_state(AdminStates.waiting_edit_answer_text)
    await state.update_data(
        back_to="answer_detail",
        answer_id=answer_id,
        question_id=question_id,
        lesson_id=lesson_id,
        topic_id=topic_id,
        message_id=callback.message.message_id,
        is_photo_message=is_photo,
    )
    if is_photo:
        await callback.message.edit_caption(
            caption="✏️ Введите новый текст варианта ответа:",
            reply_markup=cancel_kb()
        )
    else:
        await callback.message.edit_text(
            "✏️ Введите новый текст варианта ответа:",
            reply_markup=cancel_kb()
        )


@router.message(AdminStates.waiting_edit_answer_text, F.text)
async def process_edit_answer_text(
    message: Message, state: FSMContext, bot: Bot
):
    data = await state.get_data()
    msg_id = data["message_id"]
    answer_id = data["answer_id"]
    question_id = data["question_id"]
    lesson_id = data["lesson_id"]
    topic_id = data["topic_id"]
    is_photo = data.get("is_photo_message", False)
    new_text = message.text.strip()
    await message.delete()
    await state.clear()

    async with SessionLocal() as session:
        await update_answer(session, answer_id, text=new_text)
        answer = await get_answer(session, answer_id)
    logger.info(
        "ADMIN {} | Изменён текст ответа id={}",
        message.from_user.id, answer_id
    )

    text = _answer_detail_text(answer)
    kb = answer_actions_kb(
        answer_id, question_id, lesson_id, topic_id, answer.is_correct
    )
    if is_photo:
        await bot.edit_message_caption(
            chat_id=message.chat.id, message_id=msg_id,
            caption=text, reply_markup=kb
        )
    else:
        await bot.edit_message_text(
            chat_id=message.chat.id, message_id=msg_id,
            text=text, reply_markup=kb
        )


# ── Удалить вариант ответа ────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("delete:answer:"))
async def confirm_delete_answer(callback: CallbackQuery):
    parts = callback.data.split(":")
    answer_id = int(parts[2])
    question_id = int(parts[3])
    lesson_id = int(parts[4])
    topic_id = int(parts[5])
    async with SessionLocal() as session:
        answer = await get_answer(session, answer_id)
    if not answer:
        await callback.answer("Вариант не найден", show_alert=True)
        return
    preview = answer.text[:60] + "…" if len(answer.text) > 60 else answer.text
    text = f"🗑 Удалить вариант ответа?\n\n«<b>{preview}</b>»"
    kb = confirm_delete_kb(
        confirm_cb=(
            f"confirm:delete:answer:{answer_id}:{question_id}"
            f":{lesson_id}:{topic_id}"
        ),
        cancel_cb=(
            f"answer_detail:{answer_id}:{question_id}:{lesson_id}:{topic_id}"
        ),
    )
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb)
    else:
        await callback.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith("confirm:delete:answer:"))
async def do_delete_answer(callback: CallbackQuery):
    parts = callback.data.split(":")
    answer_id = int(parts[3])
    question_id = int(parts[4])
    lesson_id = int(parts[5])
    topic_id = int(parts[6])
    async with SessionLocal() as session:
        await delete_answer(session, answer_id)
        question = await get_question_with_answers(session, question_id)
    logger.warning(
        "ADMIN {} | Удалён вариант ответа id={}", callback.from_user.id, answer_id
    )
    if not question:
        await callback.answer("Вопрос не найден", show_alert=True)
        return
    answers_text = "".join(
        f"\n{'✅' if a.is_correct else '❌'} {a.text}"
        for a in question.answers
    )
    text = (
        f"❓ <b>Вопрос:</b>\n{question.text}"
        + (f"\n\n<b>Варианты:</b>{answers_text}"
           if question.answers else "\n\n<i>Вариантов нет</i>")
    )
    kb = question_detail_kb(
        question_id, lesson_id, topic_id,
        question.answers,
        has_comment=bool(question.comment),
        has_image=bool(question.image_file_id),
    )
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb)
    else:
        await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer("Вариант удалён")


# ── Редактировать комментарий к вопросу ───────────────────────────────────────

@router.callback_query(F.data.startswith("edit:comment:"))
async def start_edit_comment(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    question_id = int(parts[2])
    lesson_id = int(parts[3])
    topic_id = int(parts[4])
    await state.set_state(AdminStates.waiting_edit_question_comment)
    await state.update_data(
        back_to="question_detail",
        question_id=question_id,
        lesson_id=lesson_id,
        topic_id=topic_id,
        message_id=callback.message.message_id,
        is_photo=bool(callback.message.photo),
    )
    text = (
        "💬 Введите новый комментарий к вопросу:\n\n"
        "<i>Он будет показан пользователю после ответа.</i>"
    )
    if callback.message.photo:
        await callback.message.edit_caption(
            caption=text, reply_markup=skip_comment_kb()
        )
    else:
        await callback.message.edit_text(
            text, reply_markup=skip_comment_kb()
        )


@router.message(AdminStates.waiting_edit_question_comment, F.text)
async def process_edit_comment(
    message: Message, state: FSMContext, bot: Bot
):
    data = await state.get_data()
    question_id = data["question_id"]
    lesson_id = data["lesson_id"]
    topic_id = data["topic_id"]
    msg_id = data["message_id"]
    is_photo = data["is_photo"]
    comment = message.text.strip()
    await message.delete()
    await state.clear()

    async with SessionLocal() as session:
        await update_question_comment(session, question_id, comment)
        question = await get_question_with_answers(session, question_id)

    answers_text = "".join(
        f"\n{'✅' if a.is_correct else '❌'} {a.text}"
        for a in question.answers
    )
    text = (
        f"❓ <b>Вопрос:</b>\n{question.text}"
        + (f"\n\n<b>Варианты:</b>{answers_text}"
           if question.answers else "\n\n<i>Вариантов нет</i>")
    )
    kb = question_detail_kb(
        question_id, lesson_id, topic_id,
        question.answers,
        has_comment=bool(question.comment),
        has_image=bool(question.image_file_id),
    )
    if is_photo:
        await bot.edit_message_caption(
            chat_id=message.chat.id, message_id=msg_id,
            caption=text, reply_markup=kb
        )
    else:
        await bot.edit_message_text(
            chat_id=message.chat.id, message_id=msg_id,
            text=text, reply_markup=kb
        )


@router.callback_query(
    AdminStates.waiting_edit_question_comment,
    F.data == "admin:skip_comment"
)
async def skip_edit_comment(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    question_id = data["question_id"]
    lesson_id = data["lesson_id"]
    topic_id = data["topic_id"]
    is_photo = data["is_photo"]
    await state.clear()

    async with SessionLocal() as session:
        await update_question_comment(session, question_id, None)
        question = await get_question_with_answers(session, question_id)

    answers_text = "".join(
        f"\n{'✅' if a.is_correct else '❌'} {a.text}"
        for a in question.answers
    )
    text = (
        f"❓ <b>Вопрос:</b>\n{question.text}"
        + (f"\n\n<b>Варианты:</b>{answers_text}"
           if question.answers else "\n\n<i>Вариантов нет</i>")
    )
    kb = question_detail_kb(
        question_id, lesson_id, topic_id,
        question.answers,
        has_comment=False,
        has_image=bool(question.image_file_id),
    )
    if is_photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb)
    else:
        await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer("Комментарий удалён")


# ── Изменить фото вопроса ─────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("edit:image:"))
async def start_edit_image(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    question_id = int(parts[2])
    lesson_id = int(parts[3])
    topic_id = int(parts[4])
    has_image = bool(callback.message.photo)
    await state.set_state(AdminStates.waiting_edit_question_image)
    await state.update_data(
        back_to="question_detail",
        question_id=question_id,
        lesson_id=lesson_id,
        topic_id=topic_id,
        message_id=callback.message.message_id,
        is_photo_message=has_image,
    )
    text = "🖼 Отправьте новое фото для вопроса:"
    if has_image:
        await callback.message.edit_caption(
            caption=text, reply_markup=edit_image_kb(has_image=True)
        )
    else:
        await callback.message.edit_text(
            text, reply_markup=edit_image_kb(has_image=False)
        )


@router.message(AdminStates.waiting_edit_question_image, F.photo)
async def process_edit_image(
    message: Message, state: FSMContext, bot: Bot
):
    data = await state.get_data()
    question_id = data["question_id"]
    lesson_id = data["lesson_id"]
    topic_id = data["topic_id"]
    msg_id = data["message_id"]
    file_id = message.photo[-1].file_id
    await message.delete()
    await state.clear()

    async with SessionLocal() as session:
        await update_question_image(session, question_id, file_id)
        question = await get_question_with_answers(session, question_id)

    answers_text = "".join(
        f"\n{'✅' if a.is_correct else '❌'} {a.text}"
        for a in question.answers
    )
    text = (
        f"❓ <b>Вопрос:</b>\n{question.text}"
        + (f"\n\n<b>Варианты:</b>{answers_text}"
           if question.answers else "\n\n<i>Вариантов нет</i>")
    )
    kb = question_detail_kb(
        question_id, lesson_id, topic_id,
        question.answers,
        has_comment=bool(question.comment),
        has_image=True,
    )
    logger.info(
        "ADMIN {} | Фото вопроса id={} обновлено",
        message.from_user.id, question_id
    )
    await bot.delete_message(chat_id=message.chat.id, message_id=msg_id)
    await bot.send_photo(
        chat_id=message.chat.id,
        photo=file_id,
        caption=text,
        reply_markup=kb,
    )


@router.callback_query(
    AdminStates.waiting_edit_question_image,
    F.data == "admin:remove_image"
)
async def remove_question_image(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    question_id = data["question_id"]
    lesson_id = data["lesson_id"]
    topic_id = data["topic_id"]
    msg_id = data["message_id"]
    await state.clear()

    async with SessionLocal() as session:
        await update_question_image(session, question_id, None)
        question = await get_question_with_answers(session, question_id)

    answers_text = "".join(
        f"\n{'✅' if a.is_correct else '❌'} {a.text}"
        for a in question.answers
    )
    text = (
        f"❓ <b>Вопрос:</b>\n{question.text}"
        + (f"\n\n<b>Варианты:</b>{answers_text}"
           if question.answers else "\n\n<i>Вариантов нет</i>")
    )
    kb = question_detail_kb(
        question_id, lesson_id, topic_id,
        question.answers,
        has_comment=bool(question.comment),
        has_image=False,
    )
    logger.info(
        "ADMIN {} | Фото вопроса id={} удалено",
        callback.from_user.id, question_id
    )
    await bot.delete_message(
        chat_id=callback.message.chat.id, message_id=msg_id
    )
    await callback.message.answer(text, reply_markup=kb)
    await callback.answer("Фото удалено")

