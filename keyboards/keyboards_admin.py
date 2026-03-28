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


def menu_admin() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Конструктор тем", callback_data="topics:0")
    builder.button(
        text="Режим пользователя", callback_data="user:topics:0"
    )
    builder.adjust(1)
    return builder.as_markup()


def topics_kb(topics: list, page: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for topic in _paginate(topics, page):
        builder.button(
            text=topic.title,
            callback_data=f"lessons:{topic.id}:0"
        )
    builder.adjust(1)

    nav = _nav_row(
        topics, page,
        prev_cb=f"topics:{page - 1}",
        next_cb=f"topics:{page + 1}",
    )
    if nav:
        builder.row(*nav)

    builder.row(InlineKeyboardButton(
        text="➕ Добавить тему", callback_data="create:topic"
    ))
    builder.row(InlineKeyboardButton(
        text="🏠 Главное меню", callback_data="main_menu"
    ))
    return builder.as_markup()


def lessons_kb(
    topic_id: int, lessons: list, page: int = 0
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for lesson in _paginate(lessons, page):
        builder.button(
            text=lesson.title,
            callback_data=f"questions:{lesson.id}:0:{topic_id}"
        )
    builder.adjust(1)

    nav = _nav_row(
        lessons, page,
        prev_cb=f"lessons:{topic_id}:{page - 1}",
        next_cb=f"lessons:{topic_id}:{page + 1}",
    )
    if nav:
        builder.row(*nav)

    builder.row(InlineKeyboardButton(
        text="🔙 К темам", callback_data="topics:0"
    ))
    builder.row(
        InlineKeyboardButton(
            text="➕ Добавить урок",
            callback_data=f"create:lesson:{topic_id}"
        ),
        InlineKeyboardButton(
            text="🗑 Удалить тему",
            callback_data=f"delete:topic:{topic_id}"
        ),
    )
    return builder.as_markup()


def questions_kb(
    lesson_id: int, topic_id: int, questions: list, page: int = 0
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for q in _paginate(questions, page):
        preview = q.text[:35] + "…" if len(q.text) > 35 else q.text
        builder.button(
            text=preview,
            callback_data=f"question_detail:{q.id}:{lesson_id}:{topic_id}"
        )
    builder.adjust(1)

    nav = _nav_row(
        questions, page,
        prev_cb=f"questions:{lesson_id}:{page - 1}:{topic_id}",
        next_cb=f"questions:{lesson_id}:{page + 1}:{topic_id}",
    )
    if nav:
        builder.row(*nav)

    builder.row(InlineKeyboardButton(
        text="🔙 К урокам",
        callback_data=f"lessons:{topic_id}:0"
    ))
    builder.row(
        InlineKeyboardButton(
            text="➕ Добавить вопрос",
            callback_data=f"create:question:{lesson_id}:{topic_id}"
        ),
        InlineKeyboardButton(
            text="🗑 Удалить урок",
            callback_data=f"delete:lesson:{lesson_id}:{topic_id}"
        ),
    )
    return builder.as_markup()


def question_detail_kb(
    question_id: int,
    lesson_id: int,
    topic_id: int,
    answers: list,
    has_comment: bool = False,
    has_image: bool = False,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for ans in answers:
        mark = "✅" if ans.is_correct else "❌"
        preview = ans.text[:30] + "…" if len(ans.text) > 30 else ans.text
        builder.button(
            text=f"{mark} {preview}",
            callback_data=(
                f"answer_detail:{ans.id}:{question_id}:{lesson_id}:{topic_id}"
            )
        )
    builder.adjust(1)

    builder.row(InlineKeyboardButton(
        text="➕ Добавить вариант",
        callback_data=(
            f"create:answer:{question_id}:{lesson_id}:{topic_id}"
        )
    ))
    comment_label = "✏️ Изменить комментарий" if has_comment else "💬 Добавить комментарий"
    builder.row(InlineKeyboardButton(
        text=comment_label,
        callback_data=(
            f"edit:comment:{question_id}:{lesson_id}:{topic_id}"
        )
    ))
    image_label = "🖼 Изменить фото" if has_image else "🖼 Добавить фото"
    builder.row(InlineKeyboardButton(
        text=image_label,
        callback_data=(
            f"edit:image:{question_id}:{lesson_id}:{topic_id}"
        )
    ))
    builder.row(
        InlineKeyboardButton(
            text="🗑 Удалить вопрос",
            callback_data=(
                f"delete:question:{question_id}:{lesson_id}:{topic_id}"
            )
        ),
        InlineKeyboardButton(
            text="🔙 К вопросам",
            callback_data=f"questions:{lesson_id}:0:{topic_id}"
        ),
    )
    return builder.as_markup()


def answer_actions_kb(
    answer_id: int,
    question_id: int,
    lesson_id: int,
    topic_id: int,
    is_correct: bool,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    toggle_label = "✅ Сделать правильным" if not is_correct else "❌ Сделать неправильным"
    builder.button(
        text="✏️ Изменить текст",
        callback_data=(
            f"edit:answer:{answer_id}:{question_id}:{lesson_id}:{topic_id}"
        )
    )
    builder.button(
        text=toggle_label,
        callback_data=(
            f"toggle:answer:{answer_id}:{question_id}:{lesson_id}:{topic_id}"
        )
    )
    builder.button(
        text="🗑 Удалить вариант",
        callback_data=(
            f"delete:answer:{answer_id}:{question_id}:{lesson_id}:{topic_id}"
        )
    )
    builder.button(
        text="🔙 Назад к вопросу",
        callback_data=(
            f"question_detail:{question_id}:{lesson_id}:{topic_id}"
        )
    )
    builder.adjust(1)
    return builder.as_markup()


def confirm_delete_kb(
    confirm_cb: str, cancel_cb: str
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Да, удалить", callback_data=confirm_cb
    )
    builder.button(
        text="❌ Отмена", callback_data=cancel_cb
    )
    builder.adjust(2)
    return builder.as_markup()


def skip_comment_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="⏭ Пропустить (без комментария)",
        callback_data="admin:skip_comment"
    )
    builder.button(text="❌ Отмена", callback_data="admin:cancel")
    builder.adjust(1)
    return builder.as_markup()


def skip_image_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="⏭ Пропустить (без фото)",
        callback_data="admin:skip_image"
    )
    builder.button(text="❌ Отмена", callback_data="admin:cancel")
    builder.adjust(1)
    return builder.as_markup()


def edit_image_kb(has_image: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if has_image:
        builder.button(
            text="🗑 Удалить фото",
            callback_data="admin:remove_image"
        )
    builder.button(text="❌ Отмена", callback_data="admin:cancel")
    builder.adjust(1)
    return builder.as_markup()


def cancel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="admin:cancel")
    return builder.as_markup()


def answer_correct_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Правильный", callback_data="admin:answer_correct:yes"
    )
    builder.button(
        text="❌ Неправильный", callback_data="admin:answer_correct:no"
    )
    builder.adjust(2)
    return builder.as_markup()
