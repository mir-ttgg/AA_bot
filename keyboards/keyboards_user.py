from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
PER_PAGE = 5


def _paginate(items: list, page: int) -> list:
    start = page * PER_PAGE
    return items[start: start + PER_PAGE]


def _total_pages(items: list) -> int:
    return max(0, (len(items) - 1) // PER_PAGE) if items else 0


def _nav_row(
    items: list, page: int, prev_cb: str, next_cb: str
) -> list[InlineKeyboardButton]:
    """Возвращает строку пагинации только если страниц > 1."""
    total = _total_pages(items)
    if total == 0:
        return []
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=prev_cb))
    nav.append(InlineKeyboardButton(
        text=f"{page + 1}/{total + 1}", callback_data="noop"
    ))
    if page < total:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=next_cb))
    return nav


def user_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="📖 Начать обучение", callback_data="user:topics:0"
    )
    builder.adjust(1)
    return builder.as_markup()


def random_quiz_count_kb(topic_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for n in [5, 10, 20]:
        builder.button(
            text=f"🎲 {n} вопросов",
            callback_data=f"user:random_quiz:{topic_id}:{n}"
        )
    builder.button(text="🔙 К урокам", callback_data=f"user:lessons:{topic_id}:0")
    builder.adjust(1)
    return builder.as_markup()


def user_topics_kb(topics: list, page: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for topic in _paginate(topics, page):
        builder.button(
            text=topic.title,
            callback_data=f"user:lessons:{topic.id}:0"
        )
    builder.adjust(1)

    nav = _nav_row(
        topics, page,
        prev_cb=f"user:topics:{page - 1}",
        next_cb=f"user:topics:{page + 1}",
    )
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(
        text="В меню", callback_data="user:back_to_start"
    ))
    return builder.as_markup()


def user_lessons_kb(
    topic_id: int, lessons: list, page: int = 0
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for lesson in _paginate(lessons, page):
        builder.button(
            text=lesson.title,
            callback_data=f"user:lesson:{lesson.id}:{topic_id}"
        )
    builder.adjust(1)

    nav = _nav_row(
        lessons, page,
        prev_cb=f"user:lessons:{topic_id}:{page - 1}",
        next_cb=f"user:lessons:{topic_id}:{page + 1}",
    )
    if nav:
        builder.row(*nav)

    builder.row(InlineKeyboardButton(
        text="🎲 Случайный тест", callback_data=f"user:random_quiz_menu:{topic_id}"
    ))
    builder.row(InlineKeyboardButton(
        text="🔙 К темам", callback_data="user:topics:0"
    ))
    return builder.as_markup()


def user_lesson_kb(
    lesson_id: int, topic_id: int, question_count: int
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if question_count > 0:
        builder.button(
            text=f"▶️ Начать тест ({question_count} вопр.)",
            callback_data=f"user:start_quiz:{lesson_id}"
        )
    builder.button(
        text="🔙 К урокам",
        callback_data=f"user:lessons:{topic_id}:0"
    )
    builder.adjust(1)
    return builder.as_markup()


def quiz_question_kb(
    answers: list,
    n_correct: int = 1,
    selected_ids: list = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    selected_set = set(selected_ids or [])
    for ans in answers:
        if n_correct == 1:
            builder.button(
                text=ans.text,
                callback_data=f"user:answer:{ans.id}"
            )
        else:
            prefix = "✅ " if ans.id in selected_set else ""
            builder.button(
                text=f"{prefix}{ans.text}",
                callback_data=f"user:toggle:{ans.id}"
            )
    builder.adjust(1)
    if n_correct > 1:
        builder.row(InlineKeyboardButton(
            text="✔️ Ответить", callback_data="user:submit_answers"
        ))
    builder.row(InlineKeyboardButton(
        text="В меню", callback_data="user:back_to_start"
    ))
    return builder.as_markup()


def quiz_next_kb(is_last: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_last:
        builder.button(
            text="📊 Результаты", callback_data="user:show_result"
        )
    else:
        builder.button(
            text="➡️ Следующий вопрос",
            callback_data="user:next_question"
        )
    builder.button(text="В меню", callback_data="user:back_to_start")
    builder.adjust(1)
    return builder.as_markup()
