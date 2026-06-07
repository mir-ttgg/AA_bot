from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    from database.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # create_all не добавляет колонки в уже существующие таблицы —
        # добавляем новую колонку идемпотентно (для старых установок).
        await conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
            "onboarded BOOLEAN NOT NULL DEFAULT false"
        ))
