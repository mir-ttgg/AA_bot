import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import (
    Topic, Lesson, Question, AnswerOption, User, UserProgress
)


# ── Topic ─────────────────────────────────────────────────────────────────────

async def create_topic(session: AsyncSession, title: str) -> Topic:
    topic = Topic(title=title)
    session.add(topic)
    await session.commit()
    await session.refresh(topic)
    return topic


async def get_topics(session: AsyncSession) -> list[Topic]:
    result = await session.execute(select(Topic).order_by(Topic.id))
    return list(result.scalars().all())


async def get_topic(session: AsyncSession, topic_id: int) -> Topic | None:
    return await session.get(Topic, topic_id)


async def update_topic(session: AsyncSession, topic_id: int, title: str) -> bool:
    topic = await session.get(Topic, topic_id)
    if not topic:
        return False
    topic.title = title
    await session.commit()
    return True


async def delete_topic(session: AsyncSession, topic_id: int) -> bool:
    topic = await session.get(Topic, topic_id)
    if not topic:
        return False
    await session.delete(topic)
    await session.commit()
    return True


# ── Lesson ────────────────────────────────────────────────────────────────────

async def create_lesson(
    session: AsyncSession, title: str, topic_id: int
) -> Lesson:
    lesson = Lesson(title=title, topic_id=topic_id)
    session.add(lesson)
    await session.commit()
    await session.refresh(lesson)
    return lesson


async def get_lessons(session: AsyncSession, topic_id: int) -> list[Lesson]:
    result = await session.execute(
        select(Lesson).where(Lesson.topic_id == topic_id).order_by(Lesson.id)
    )
    return list(result.scalars().all())


async def get_lesson(session: AsyncSession, lesson_id: int) -> Lesson | None:
    return await session.get(Lesson, lesson_id)


async def update_lesson(
    session: AsyncSession, lesson_id: int, title: str
) -> bool:
    lesson = await session.get(Lesson, lesson_id)
    if not lesson:
        return False
    lesson.title = title
    await session.commit()
    return True


async def delete_lesson(session: AsyncSession, lesson_id: int) -> bool:
    lesson = await session.get(Lesson, lesson_id)
    if not lesson:
        return False
    await session.delete(lesson)
    await session.commit()
    return True


# ── Question ──────────────────────────────────────────────────────────────────

async def create_question(
    session: AsyncSession,
    text: str,
    lesson_id: int,
    image_file_id: str | None = None,
    comment: str | None = None,
) -> Question:
    question = Question(
        text=text, lesson_id=lesson_id, image_file_id=image_file_id,
        comment=comment,
    )
    session.add(question)
    await session.commit()
    await session.refresh(question)
    return question


async def update_question_comment(
    session: AsyncSession, question_id: int, comment: str | None
) -> bool:
    question = await session.get(Question, question_id)
    if not question:
        return False
    question.comment = comment
    await session.commit()
    return True


async def update_question_image(
    session: AsyncSession, question_id: int, image_file_id: str | None
) -> bool:
    question = await session.get(Question, question_id)
    if not question:
        return False
    question.image_file_id = image_file_id
    await session.commit()
    return True


async def get_questions(session: AsyncSession, lesson_id: int) -> list[Question]:
    result = await session.execute(
        select(Question)
        .where(Question.lesson_id == lesson_id)
        .order_by(Question.id)
    )
    return list(result.scalars().all())


async def get_question(
    session: AsyncSession, question_id: int
) -> Question | None:
    return await session.get(Question, question_id)


async def get_question_with_answers(
    session: AsyncSession, question_id: int
) -> Question | None:
    result = await session.execute(
        select(Question)
        .where(Question.id == question_id)
        .options(selectinload(Question.answers))
    )
    return result.scalar_one_or_none()


async def update_question(
    session: AsyncSession, question_id: int, text: str
) -> bool:
    question = await session.get(Question, question_id)
    if not question:
        return False
    question.text = text
    await session.commit()
    return True


async def delete_question(session: AsyncSession, question_id: int) -> bool:
    question = await session.get(Question, question_id)
    if not question:
        return False
    await session.delete(question)
    await session.commit()
    return True


# ── AnswerOption ──────────────────────────────────────────────────────────────

async def create_answer(
    session: AsyncSession, question_id: int, text: str, is_correct: bool = False
) -> AnswerOption:
    answer = AnswerOption(
        question_id=question_id, text=text, is_correct=is_correct
    )
    session.add(answer)
    await session.commit()
    await session.refresh(answer)
    return answer


async def get_answers(
    session: AsyncSession, question_id: int
) -> list[AnswerOption]:
    result = await session.execute(
        select(AnswerOption).where(AnswerOption.question_id == question_id)
    )
    return list(result.scalars().all())


async def get_answer(
    session: AsyncSession, answer_id: int
) -> AnswerOption | None:
    return await session.get(AnswerOption, answer_id)


async def update_answer(
    session: AsyncSession,
    answer_id: int,
    text: str | None = None,
    is_correct: bool | None = None,
) -> bool:
    answer = await session.get(AnswerOption, answer_id)
    if not answer:
        return False
    if text is not None:
        answer.text = text
    if is_correct is not None:
        answer.is_correct = is_correct
    await session.commit()
    return True


async def delete_answer(session: AsyncSession, answer_id: int) -> bool:
    answer = await session.get(AnswerOption, answer_id)
    if not answer:
        return False
    await session.delete(answer)
    await session.commit()
    return True


# ── User ──────────────────────────────────────────────────────────────────────

async def get_or_create_user(
    session: AsyncSession, user_id: int, username: str | None = None
) -> User:
    user = await session.get(User, user_id)
    if not user:
        user = User(id=user_id, username=username)
        session.add(user)
        await session.commit()
    return user


# ── UserProgress ──────────────────────────────────────────────────────────────

async def save_progress(
    session: AsyncSession,
    user_id: int,
    question_id: int,
    chosen_answer_id: int | None,
    is_correct: bool,
) -> UserProgress:
    record = UserProgress(
        user_id=user_id,
        question_id=question_id,
        chosen_answer_id=chosen_answer_id,
        is_correct=is_correct,
    )
    session.add(record)
    await session.commit()
    return record


# ── Случайные вопросы для теста ───────────────────────────────────────────────

async def get_random_questions_for_quiz(
    session: AsyncSession, count: int = 10
) -> list[Question]:
    """
    Возвращает случайные вопросы из всей базы.
    Берёт только те, у которых есть хотя бы 1 правильный
    и хотя бы 1 неправильный ответ в пуле.
    """
    result = await session.execute(
        select(Question).options(selectinload(Question.answers))
    )
    all_questions = list(result.scalars().all())

    valid = [
        q for q in all_questions
        if any(a.is_correct for a in q.answers)
        and any(not a.is_correct for a in q.answers)
    ]
    if not valid:
        return []
    return random.sample(valid, min(count, len(valid)))
