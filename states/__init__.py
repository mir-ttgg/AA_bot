from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    waiting_topic_title = State()
    waiting_lesson_title = State()
    waiting_question_text = State()
    waiting_question_image = State()
    waiting_question_comment = State()
    waiting_edit_question_comment = State()
    waiting_answer_text = State()
    waiting_answer_correct = State()
    waiting_edit_answer_text = State()
    waiting_edit_question_image = State()


class UserStates(StatesGroup):
    in_quiz = State()
