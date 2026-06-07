from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from loguru import logger

from database.session import SessionLocal
from database.crud import get_or_create_user
from keyboards.keyboards_admin import menu_admin
from keyboards.keyboards_user import start_button_kb, main_menu_kb
from services import emoji, content

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, is_admin: bool, state: FSMContext):
    await state.clear()
    user = message.from_user
    async with SessionLocal() as session:
        db_user = await get_or_create_user(session, user.id, user.username)
        onboarded = db_user.onboarded

    name = user.first_name or "Пользователь"
    tag = f"@{user.username}" if user.username else f"id={user.id}"

    if is_admin:
        logger.info("ADMIN /start | {} {}", user.id, tag)
        await message.answer(
            f"{emoji.EMOJI_HELLO} <b>{name}</b>, добро пожаловать в панель "
            f"администратора!{emoji.EMOJI_DANIL}\nВыберите действие:",
            reply_markup=menu_admin()
        )
        return

    if not onboarded:
        logger.info("USER  /start (онбординг) | {} {}", user.id, tag)
        await message.answer(
            content.WELCOME_TEXT, reply_markup=start_button_kb()
        )
    else:
        logger.info("USER  /start (меню) | {} {}", user.id, tag)
        await message.answer(
            f"{emoji.EMOJI_HOME} <b>Главное меню</b>\n\nВыбери режим:",
            reply_markup=main_menu_kb(),
        )


@router.message(Command("onboarding"))
async def cmd_onboarding(message: Message, is_admin: bool, state: FSMContext):
    """Запуск онбординга для проверки (только для админов)."""
    if not is_admin:
        return
    await state.clear()
    logger.info("ADMIN /onboarding | {}", message.from_user.id)
    await message.answer(
        content.WELCOME_TEXT, reply_markup=start_button_kb()
    )


@router.message(Command("help"))
async def cmd_help(message: Message, is_admin: bool):
    logger.info("HELP | {} {}", message.from_user.id,
                message.from_user.username)
    if is_admin:
        text = (
            "<b>Помощь — режим администратора</b>\n\n"
            "<b>Конструктор:</b>\n"
            "• Темы → Уроки → Вопросы — иерархия контента\n"
            "• У каждого вопроса пул ответов: минимум 1 правильный и 3 неправильных\n"
            "• К вопросу можно прикрепить фото\n"
            "• Ответы можно редактировать: менять текст, переключать правильность, удалять\n\n"
            "<b>Команды:</b>\n"
            "/start — главное меню\n"
            "/onboarding — проверить вступительный тест\n"
            "/help — эта подсказка\n\n"
            "<b>Подсказки:</b>\n"
            "• Нажмите на вариант ответа, чтобы открыть его настройки\n"
            "• Удаление темы удаляет все уроки и вопросы внутри\n"
            "• Фото к вопросу можно пропустить при создании"
        )
    else:
        text = (
            f"{emoji.EMOGI_QUESTION} <b>Помощь</b>\n\n"
            "<b>Режимы тренировки:</b>\n"
            "• <b>Библиотека</b> — листай ЭКГ по темам и жми "
            "«Показать ответ», чтобы увидеть разбор\n"
            "• <b>Дежурство</b> — выбери количество ЭКГ, отвечай на "
            "вопросы и получай баллы в рейтинг\n"
            "• <b>Профиль</b> — твой ранг, место в рейтинге, "
            "статистика и поддержка\n\n"
            "<b>Команды:</b>\n"
            "/start — вернуться в главное меню\n"
            "/help — эта подсказка"
        )
    await message.answer(text)
