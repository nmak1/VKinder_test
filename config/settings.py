import os
from dataclasses import dataclass, field
from dotenv import load_dotenv
from typing import List

load_dotenv()


@dataclass
class Settings:
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN")
    VK_TOKEN: str = os.getenv("VK_TOKEN")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///vkinder.db")
    SEARCH_LIMIT: int = int(os.getenv("SEARCH_LIMIT", 50))
    PHOTOS_LIMIT: int = int(os.getenv("PHOTOS_LIMIT", 3))
    REQUEST_DELAY: float = float(os.getenv("REQUEST_DELAY", 0.34))
    ADMIN_IDS: List[int] = field(default_factory=list)

    def __post_init__(self):
        if os.getenv("ADMIN_IDS"):
            self.ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS").split(",")))
    @classmethod
    def validate(cls):
        if not cls.TELEGRAM_TOKEN:
            raise ValueError("TELEGRAM_TOKEN не задан")
        if not cls.VK_TOKEN:
            raise ValueError("VK_TOKEN не задан")


settings = Settings()
