import telebot
from telebot import types
from database.manager import DatabaseManager
from services.vk_service import VKService
from services.search_service import SearchService
from services.notification_service import NotificationService
from config.settings import settings
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class VKinderBot:
    def __init__(self):
        self.bot = telebot.TeleBot(settings.TELEGRAM_TOKEN)
        self.db = DatabaseManager(settings.DATABASE_URL)
        self.vk_service = VKService()
        self.search_service = SearchService(self.vk_service, self.db)
        self.notifier = NotificationService(self.bot, settings.ADMIN_IDS)

        if not self.db.health_check():
            raise RuntimeError("Database connection failed")

        self._register_handlers()
        logger.info("Bot initialized")

    def _register_handlers(self):
        @self.bot.message_handler(commands=['start'])
        def handle_start(message):
            self._handle_start(message)

        # ... другие обработчики ...

    def _handle_start(self, message: types.Message):
        try:
            user_id = message.from_user.id
            user = self.db.get_or_create_user(
                user_id,
                message.from_user.first_name,
                message.from_user.last_name
            )

            self.bot.send_message(
                message.chat.id,
                f"Привет, {user.first_name}!",
                reply_markup=self._main_keyboard()
            )
        except Exception as e:
            logger.error(f"Start failed: {e}")
            self.notifier.send_admin(f"Start failed for {user_id}: {e}")

    # ... остальные методы бота ...

    def run(self):
        logger.info("Starting bot polling...")
        self.bot.polling(none_stop=True)