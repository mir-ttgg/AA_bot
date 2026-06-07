from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.fsm.context import FSMContext
from loguru import logger

from database.session import SessionLocal
from database.crud import mark_onboarded
from keyboards.keyboards_user import (
    onboarding_answer_kb,
    onboarding_next_kb,
    onboarding_result_kb,
    onboarding_tutorial_kb,
    main_menu_kb,
)
from states import UserStates
from services import content
from services.ui import safe_delete

router = Router()

# Кэш file_id для картинок онбординга, чтобы не загружать их повторно.
_PHOTO_CACHE: dict[str, str] = {}


async def _send_question(message: Message, index: int) -> None:
    """Отправляет новое сообщение с ЭКГ-вопросом онбординга."""
    q = content.ONBOARDING_QUESTIONS[index]
    total = len(content.ONBOARDING_QUESTIONS)
    caption = (
        f"<b>ЭКГ №{index + 1}/{total}</b>\n\n{q['question']}"
    )
    kb = onboarding_answer_kb()

    cached = _PHOTO_CACHE.get(q["image"])
    if cached:
        await message.answer_photo(cached, caption=caption, reply_markup=kb)
        return

    path = content.ASSETS_DIR / q["image"]
    if path.exists():
        sent = await message.answer_photo(
            FSInputFile(path), caption=caption, reply_markup=kb
        )
        if sent.photo:
            _PHOTO_CACHE[q["image"]] = sent.photo[-1].file_id
    else:
        logger.warning("Нет файла ЭКГ для онбординга: {}", path)
        await message.answer(caption, reply_markup=kb)


# ── Старт онбординга (кнопка «Начать!») ───────────────────────────────────────

@router.callback_query(F.data == "onb:start")
async def onb_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.onboarding)
    await state.update_data(onb_index=0, onb_correct=0)
    logger.info("USER {} | Онбординг начат", callback.from_user.id)
    await safe_delete(callback.message)
    await _send_question(callback.message, 0)
    await callback.answer()


# ── Ответ на вопрос онбординга ────────────────────────────────────────────────

@router.callback_query(UserStates.onboarding, F.data.startswith("onb:ans:"))
async def onb_answer(callback: CallbackQuery, state: FSMContext):
    choice = callback.data.split(":")[2]
    data = await state.get_data()
    index = data.get("onb_index", 0)
    correct_count = data.get("onb_correct", 0)
    q = content.ONBOARDING_QUESTIONS[index]

    if choice == q["correct"]:
        correct_count += 1
    await state.update_data(onb_correct=correct_count)

    await safe_delete(callback.message)
    await callback.message.answer(
        q["explanation"], reply_markup=onboarding_next_kb()
    )
    await callback.answer()


# ── Кнопка «Дальше» после разбора ─────────────────────────────────────────────

@router.callback_query(UserStates.onboarding, F.data == "onb:next")
async def onb_next(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    index = data.get("onb_index", 0) + 1
    total = len(content.ONBOARDING_QUESTIONS)

    await safe_delete(callback.message)
    if index < total:
        await state.update_data(onb_index=index)
        await _send_question(callback.message, index)
    else:
        correct = data.get("onb_correct", 0)
        logger.info(
            "USER {} | Онбординг-тест завершён | {}/{}",
            callback.from_user.id, correct, total
        )
        await callback.message.answer(
            content.ONBOARDING_RESULTS.get(correct, content.ONBOARDING_RESULTS[0]),
            reply_markup=onboarding_result_kb(),
        )
    await callback.answer()


# ── Обучающий экран ───────────────────────────────────────────────────────────

@router.callback_query(UserStates.onboarding, F.data == "onb:tutorial")
async def onb_tutorial(callback: CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    await callback.message.answer(
        content.TUTORIAL_TEXT, reply_markup=onboarding_tutorial_kb()
    )
    await callback.answer()


# ── Завершение онбординга → главное меню ──────────────────────────────────────

@router.callback_query(F.data == "onb:finish")
async def onb_finish(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    async with SessionLocal() as session:
        await mark_onboarded(session, callback.from_user.id)
    logger.info("USER {} | Онбординг пройден", callback.from_user.id)
    await safe_delete(callback.message)
    await callback.message.answer(
        "<b>Главное меню</b>\n\nВыбери режим:",
        reply_markup=main_menu_kb(),
    )
    await callback.answer()
