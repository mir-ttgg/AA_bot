from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from loguru import logger

from database.session import SessionLocal
from database.crud import mark_onboarded
from keyboards.keyboards_user import (
    start_button_kb,
    onboarding_answer_kb,
    onboarding_next_kb,
    onboarding_result_kb,
    onboarding_tutorial_kb,
    main_menu_kb,
)
from states import UserStates
from services import content, emoji
from services.ui import safe_delete

router = Router()

# Кэш file_id для картинок онбординга, чтобы не загружать их повторно.
_PHOTO_CACHE: dict[str, str] = {}


async def _send_photo(message: Message, filename: str, caption: str, kb) -> None:
    """Шлёт фото из assets/onboarding с подписью; кэширует file_id.
    Если файла нет — отправляет подпись текстом."""
    cached = _PHOTO_CACHE.get(filename)
    if cached:
        await message.answer_photo(cached, caption=caption, reply_markup=kb)
        return

    path = content.ASSETS_DIR / filename
    if path.exists():
        sent = await message.answer_photo(
            FSInputFile(path), caption=caption, reply_markup=kb
        )
        if sent.photo:
            _PHOTO_CACHE[filename] = sent.photo[-1].file_id
    else:
        logger.warning("Нет файла для онбординга: {}", path)
        await message.answer(caption, reply_markup=kb)


async def _send_question(message: Message, index: int) -> None:
    """Отправляет новое сообщение с ЭКГ-вопросом онбординга."""
    q = content.ONBOARDING_QUESTIONS[index]
    total = len(content.ONBOARDING_QUESTIONS)
    caption = f"<b>ЭКГ №{index + 1}/{total}</b>\n\n{q['question']}"
    await _send_photo(message, q["image"], caption, onboarding_answer_kb())


# ── Предпросмотр онбординга (для админов) ─────────────────────────────────────

@router.callback_query(F.data == "onb:preview")
async def onb_preview(callback: CallbackQuery, state: FSMContext):
    """Показывает онбординг с самого начала (приветствие + «Начать!»)."""
    await state.clear()
    await safe_delete(callback.message)
    await callback.message.answer(
        content.WELCOME_TEXT, reply_markup=start_button_kb()
    )
    await callback.answer()


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

    # Оставляем ЭКГ на экране: меняем подпись на разбор (он влезает в лимит).
    explanation = q["explanation"]
    kb = onboarding_next_kb()
    msg = callback.message
    if msg.photo:
        try:
            await msg.edit_caption(caption=explanation, reply_markup=kb)
        except TelegramBadRequest:
            # на всякий случай: разбор не влез — оставляем фото, текст ниже
            await msg.edit_reply_markup(reply_markup=None)
            await msg.answer(explanation, reply_markup=kb)
    else:
        await msg.edit_text(explanation, reply_markup=kb)
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
    await _send_photo(
        callback.message,
        content.TUTORIAL_IMAGE,
        content.TUTORIAL_TEXT,
        onboarding_tutorial_kb(),
    )
    await callback.answer()


# ── Завершение онбординга → главное меню ──────────────────────────────────────

@router.callback_query(F.data == "onb:finish")
async def onb_finish(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    async with SessionLocal() as session:
        await mark_onboarded(session, callback.from_user.id)
    logger.info("USER {} | Онбординг пройден", callback.from_user.id)
    # Обучающее сообщение со схемой оставляем в чате — только убираем кнопку,
    # чтобы её нельзя было нажать повторно.
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.message.answer(
        f"{emoji.EMOJI_RED_2} <b>Главное меню</b>\n\nВыбери режим:",
        reply_markup=main_menu_kb(),
    )
    await callback.answer()
