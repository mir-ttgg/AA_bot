from datetime import datetime
from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey,
    Integer, String, Text, func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now())

    lessons: Mapped[list["Lesson"]] = relationship(
        back_populates="topic", cascade="all, delete-orphan")


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey(
        "topics.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now())

    topic: Mapped["Topic"] = relationship(back_populates="lessons")
    questions: Mapped[list["Question"]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey(
        "lessons.id", ondelete="CASCADE"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    image_file_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now())

    lesson: Mapped["Lesson"] = relationship(back_populates="questions")
    answers: Mapped[list["AnswerOption"]] = relationship(
        back_populates="question", cascade="all, delete-orphan")
    user_progress: Mapped[list["UserProgress"]
                          ] = relationship(back_populates="question", cascade="all, delete-orphan")


class AnswerOption(Base):
    __tablename__ = "answer_options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey(
        "questions.id", ondelete="CASCADE"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False)

    question: Mapped["Question"] = relationship(back_populates="answers")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True) 
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now())

    progress: Mapped[list["UserProgress"]
                     ] = relationship(back_populates="user")


class UserProgress(Base):
    """Каждый ответ пользователя — отдельная запись."""
    __tablename__ = "user_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(
        "users.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey(
        "questions.id", ondelete="CASCADE"), nullable=False)
    chosen_answer_id: Mapped[int | None] = mapped_column(
        ForeignKey("answer_options.id"), nullable=True)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="progress")
    question: Mapped["Question"] = relationship(back_populates="user_progress")
    chosen_answer: Mapped["AnswerOption | None"] = relationship()
