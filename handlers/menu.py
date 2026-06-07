from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from loguru import logger

from config import SUPPORT_CONTACT
from database.session import SessionLocal
from database.crud import (
    get_user_stats,
    get_best_duty,
    get_overall_place,
    get_weekly_place,
)
from keyboards.keyboards_user import (
    main_menu_kb,
    profile_kb,
    back_to_menu_kb,
)
from services import content, emoji
from services.ui import show

router = Router()


# ── Главное меню ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:main")
async def open_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await show(
        callback,
        f"{emoji.EMOJI_HOME} <b>Главное меню</b>\n\nВыбери режим:",
        reply_markup=main_menu_kb(),
    )
    await callback.answer()


# ── Профиль ───────────────────────────────────────────────────────────────────

def _display_name(callback: CallbackQuery) -> str:
    user = callback.from_user
    if user.username:
        return user.username
    return user.first_name or f"id{user.id}"


@router.callback_query(F.data == "menu:profile")
async def open_profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with SessionLocal() as session:
        total, correct = await get_user_stats(session, user_id)
        best = await get_best_duty(session, user_id)
        overall = await get_overall_place(session, user_id)
        weekly = await get_weekly_place(session, user_id)

    accuracy = round(correct / total * 100) if total else 0
    rank = content.get_rank(accuracy)

    text = (
        "<b>Профиль</b>\n\n"
        f"Имя пользователя: <b>{_display_name(callback)}</b>\n"
        f"Текущий ранг: <b>{rank}</b>\n\n"
        "<b>Рейтинг</b>\n"
        f"Место среди всех пользователей: <b>{overall}</b>\n"
        f"Место за неделю: <b>{weekly}</b>\n"
        f"Лучший результат дежурства: <b>{best}%</b>\n\n"
        "<b>Результаты тренировок</b>\n"
        f"Всего разобрано ЭКГ: <b>{total}</b>\n"
        f"Правильных ответов: <b>{correct}</b>\n"
        f"Средняя точность: <b>{accuracy}%</b>"
    )
    logger.info("USER {} | Профиль открыт", user_id)
    await show(callback, text, reply_markup=profile_kb())
    await callback.answer()


@router.callback_query(F.data == "prof:ranks")
async def show_ranks(callback: CallbackQuery):
    text = (
        f"{content.RANKS_TEXT}\n\n"
        "<i>Ранг определяется средней точностью твоих ответов.</i>"
    )
    await show(callback, text, reply_markup=back_to_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "prof:support")
async def show_support(callback: CallbackQuery):
    text = (
        f"{emoji.EMOJI_WHITE_2} <b>Поддержка</b>\n\n"
        "Есть вопрос, нашёл ошибку в разборе или хочешь предложить "
        f"идею? Пиши: {SUPPORT_CONTACT}"
    )
    await show(callback, text, reply_markup=back_to_menu_kb())
    await callback.answer()
