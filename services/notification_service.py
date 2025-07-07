import logging
from typing import List, Optional
import telebot
from telebot import types

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, bot: telebot.TeleBot, admin_ids: List[int]):
        """
        Сервис для отправки уведомлений пользователям и администраторам

        :param bot: Экземпляр телеграм бота
        :param admin_ids: Список ID администраторов
        """
        self.bot = bot
        self.admin_ids = admin_ids or []
        logger.info(f"NotificationService initialized with {len(admin_ids)} admins")

    def send_admin(self, message: str, parse_mode: Optional[str] = None) -> None:
        """
        Отправляет сообщение всем администраторам

        :param message: Текст сообщения
        :param parse_mode: Режим форматирования (HTML/Markdown)
        """
        for admin_id in self.admin_ids:
            try:
                self.bot.send_message(
                    admin_id,
                    f"⚠️ ADMIN NOTIFICATION:\n{message}",
                    parse_mode=parse_mode
                )
                logger.info(f"Admin notification sent to {admin_id}")
            except Exception as e:
                logger.error(f"Failed to send admin notification to {admin_id}: {e}")

    def notify_user(self, user_id: int, message: str,
                    keyboard: Optional[types.ReplyKeyboardMarkup] = None,
                    parse_mode: Optional[str] = None) -> bool:
        """
        Отправляет уведомление пользователю

        :param user_id: ID пользователя Telegram
        :param message: Текст сообщения
        :param keyboard: Клавиатура для ответа
        :param parse_mode: Режим форматирования
        :return: Успешность отправки
        """
        try:
            self.bot.send_message(
                user_id,
                message,
                reply_markup=keyboard,
                parse_mode=parse_mode
            )
            logger.info(f"Notification sent to user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to notify user {user_id}: {e}")
            return False

    def notify_new_match(self, user_id: int, match_name: str, match_link: str) -> None:
        """
        Уведомляет пользователя о новом совпадении

        :param user_id: ID пользователя Telegram
        :param match_name: Имя совпадения
        :param match_link: Ссылка на профиль
        """
        message = (
            f"💌 Новый потенциальный матч!\n\n"
            f"👤 {match_name}\n"
            f"🔗 {match_link}"
        )
        self.notify_user(user_id, message)

    def notify_error(self, user_id: int, error_type: str = "general") -> None:
        """
        Отправляет стандартное сообщение об ошибке

        :param user_id: ID пользователя
        :param error_type: Тип ошибки (general/search/database)
        """
        messages = {
            "general": "⚠️ Произошла ошибка. Попробуйте позже.",
            "search": "🔍 Ошибка при поиске. Попробуйте изменить параметры.",
            "database": "🛠 Технические неполадки. Мы уже работаем над исправлением."
        }
        self.notify_user(user_id, messages.get(error_type, messages["general"]))