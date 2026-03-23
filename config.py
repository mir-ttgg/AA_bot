import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
DATABASE_URL: str = os.getenv("DATABASE_URL", "")
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
ADMIN_IDS: list[int] = [
    int(i) for i in os.getenv("ADMIN_IDS", "").split(",") if i.strip()
]
