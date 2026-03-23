from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from loguru import logger

from database.session import SessionLocal
from database.crud import get_or_create_user
from keyboards.keyboards_admin import menu_admin
from keyboards.keyboards_user import user_menu_kb
from services import emoji

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, is_admin: bool):
    user = message.from_user
    async with SessionLocal() as session:
        await get_or_create_user(session, user.id, user.username)

    name = user.first_name or "Пользователь"
    tag = f"@{user.username}" if user.username else f"id={user.id}"

    if is_admin:
        logger.info("ADMIN /start | {} {}", user.id, tag)
        await message.answer(
            f"{emoji.EMOJI_HELLO} <b>{name}</b>, добро пожаловать в панель администратора!{emoji.EMOJI_DANIL}\n"
            "Выберите действие:",
            reply_markup=menu_admin()
        )
    else:
        logger.info("USER  /start | {} {}", user.id, tag)
        await message.answer(
            f"{emoji.EMOJI_HELLO} <b>{name}</b>, добро пожаловать в медицинский тренажёр!\n\n"
            "Здесь ты можешь проходить тесты по медицинским темам "
            "и отслеживать свой прогресс.\n\n"
            "Нажми кнопку ниже, чтобы начать:",
            reply_markup=user_menu_kb()
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
            "/help — эта подсказка\n\n"
            "<b>Подсказки:</b>\n"
            "• Нажмите на вариант ответа, чтобы открыть его настройки\n"
            "• Удаление темы удаляет все уроки и вопросы внутри\n"
            "• Фото к вопросу можно пропустить при создании"
        )
    else:
        text = (
            f"{emoji.EMOGI_QUESTION} <b>Помощь</b>\n\n"
            "<b>Как пользоваться тренажёром:</b>\n"
            "• <b>Начать обучение</b> — выберите тему и урок, затем пройдите тест\n"
            "• <b>Случайный тест</b> — вопросы из всей базы в случайном порядке\n\n"
            "<b>Во время теста:</b>\n"
            "• Выберите один вариант ответа из предложенных\n"
            "• После ответа вы узнаете, были ли правы\n"
            "• Кнопка <b>🏠 В меню</b> позволяет выйти из теста в любой момент\n\n"
            "<b>Команды:</b>\n"
            "/start — вернуться в главное меню\n"
            "/help — эта подсказка\n\n"
            "<b>Подсказки:</b>\n"
            "• Результат показывается в конце каждого теста\n"
            "• После теста можно пройти его повторно"
        )
    await message.answer(text)
