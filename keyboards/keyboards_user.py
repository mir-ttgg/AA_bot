from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

PER_PAGE = 6


def _paginate(items: list, page: int) -> list:
    start = page * PER_PAGE
    return items[start: start + PER_PAGE]


def _total_pages(items: list) -> int:
    return max(0, (len(items) - 1) // PER_PAGE) if items else 0


def _nav_row(
    items: list, page: int, prev_cb: str, next_cb: str
) -> list[InlineKeyboardButton]:
    """Строка пагинации, только если страниц больше одной."""
    total = _total_pages(items)
    if total == 0:
        return []
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="Назад", callback_data=prev_cb))
    nav.append(InlineKeyboardButton(
        text=f"{page + 1}/{total + 1}", callback_data="noop"
    ))
    if page < total:
        nav.append(InlineKeyboardButton(text="Вперёд", callback_data=next_cb))
    return nav


# ── Онбординг ─────────────────────────────────────────────────────────────────

def start_button_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Начать!", callback_data="onb:start")
    return builder.as_markup()


def onboarding_answer_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Норма", callback_data="onb:ans:norma")
    builder.button(text="Патология", callback_data="onb:ans:patol")
    builder.adjust(2)
    return builder.as_markup()


def onboarding_next_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Дальше", callback_data="onb:next")
    return builder.as_markup()


def onboarding_result_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Дальше", callback_data="onb:tutorial")
    return builder.as_markup()


def onboarding_tutorial_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Главное меню", callback_data="onb:finish")
    return builder.as_markup()


# ── Главное меню ──────────────────────────────────────────────────────────────

def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Библиотека", callback_data="menu:library")
    builder.button(text="Дежурство", callback_data="menu:duty")
    builder.button(text="Профиль", callback_data="menu:profile")
    builder.adjust(1)
    return builder.as_markup()


# ── Библиотека ────────────────────────────────────────────────────────────────

def library_kb(topics_data: list) -> InlineKeyboardMarkup:
    """Единый список: тема (заголовок-разделитель) и её ЭКГ кнопками.

    topics_data — список кортежей (topic_id, title, count).
    Заголовок темы — некликабельная кнопка (noop), под ней ЭКГ 1..count.
    """
    builder = InlineKeyboardBuilder()
    for topic_id, title, count in topics_data:
        builder.row(InlineKeyboardButton(
            text=f"— {title} —", callback_data="noop"
        ))
        for i in range(count):
            builder.row(InlineKeyboardButton(
                text=f"ЭКГ {i + 1}",
                callback_data=f"lib:open:{topic_id}:{i}"
            ))
    builder.row(InlineKeyboardButton(
        text="Главное меню", callback_data="menu:main"
    ))
    return builder.as_markup()


def library_browse_kb(
    topic_id: int, index: int, total: int, revealed: bool
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if not revealed:
        builder.row(InlineKeyboardButton(
            text="Показать ответ",
            callback_data=f"lib:show:{topic_id}:{index}"
        ))
    nav: list[InlineKeyboardButton] = []
    if index > 0:
        nav.append(InlineKeyboardButton(
            text="Предыдущий",
            callback_data=f"lib:nav:{topic_id}:{index - 1}"
        ))
    if index < total - 1:
        nav.append(InlineKeyboardButton(
            text="Дальше",
            callback_data=f"lib:nav:{topic_id}:{index + 1}"
        ))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(
        text="Выйти", callback_data="lib:topics:0"
    ))
    return builder.as_markup()


# ── Дежурство ─────────────────────────────────────────────────────────────────

def duty_count_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for n in (5, 10, 20):
        builder.button(text=f"{n}", callback_data=f"duty:start:{n}")
    builder.adjust(3)
    builder.row(InlineKeyboardButton(
        text="Главное меню", callback_data="menu:main"
    ))
    return builder.as_markup()


def duty_question_kb(
    answers: list,
    n_correct: int = 1,
    selected_ids: list | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    selected_set = set(selected_ids or [])
    for ans in answers:
        if n_correct == 1:
            builder.button(
                text=ans.text,
                callback_data=f"duty:answer:{ans.id}"
            )
        else:
            prefix = "✓ " if ans.id in selected_set else ""
            builder.button(
                text=f"{prefix}{ans.text}",
                callback_data=f"duty:toggle:{ans.id}"
            )
    builder.adjust(1)
    if n_correct > 1:
        builder.row(InlineKeyboardButton(
            text="Ответить", callback_data="duty:submit"
        ))
    builder.row(InlineKeyboardButton(
        text="Выйти", callback_data="duty:exit"
    ))
    return builder.as_markup()


def duty_next_kb(is_last: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_last:
        builder.button(text="Завершить", callback_data="duty:result")
    else:
        builder.button(text="Дальше", callback_data="duty:next")
    builder.button(text="Выйти", callback_data="duty:exit")
    builder.adjust(1)
    return builder.as_markup()


def duty_exit_confirm_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Отмена", callback_data="duty:exit_cancel")
    builder.button(text="Выйти", callback_data="duty:exit_confirm")
    builder.adjust(2)
    return builder.as_markup()


def duty_result_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Ещё дежурство", callback_data="menu:duty")
    builder.button(text="Главное меню", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


# ── Профиль ───────────────────────────────────────────────────────────────────

def profile_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Ранги", callback_data="prof:ranks")
    builder.button(text="Поддержка", callback_data="prof:support")
    builder.button(text="Главное меню", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


def back_to_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="В профиль", callback_data="menu:profile")
    builder.button(text="Главное меню", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()
