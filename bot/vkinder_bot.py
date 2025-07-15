import logging
from typing import Dict, List, Optional

import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException

from config.settings import settings
from database.manager import DatabaseManager
from services.vk_service import VKService
from services.search_service import SearchService
from services.notification_service import NotificationService

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('vkinder_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class VKinderBot:
    def __init__(self):
        try:
            # Инициализация компонентов
            self.bot = telebot.TeleBot(settings.TELEGRAM_TOKEN)
            self.db = DatabaseManager(settings.DATABASE_URL)
            self.vk_service = VKService()
            self.search_service = SearchService(self.vk_service, self.db)
            self.notifier = NotificationService(self.bot, settings.ADMIN_IDS)

            # Проверка подключений
            if not self.db.health_check():
                raise RuntimeError("Database connection failed")

            # Состояния пользователей
            self.user_states: Dict[int, str] = {}  # user_id: state
            self.search_results: Dict[int, List[Dict]] = {}
            self.current_match_index: Dict[int, int] = {}

            # Регистрация обработчиков
            self._register_handlers()

            logger.info("VKinderBot успешно инициализирован")
        except Exception as e:
            logger.critical(f"Ошибка инициализации бота: {e}")
            raise

    def _register_handlers(self):
        """Регистрация всех обработчиков команд и сообщений"""

        @self.bot.message_handler(commands=['start'])
        def handle_start(message):
            self._handle_start_command(message)

        @self.bot.message_handler(commands=['help'])
        def handle_help(message):
            self._handle_help_command(message)

        @self.bot.message_handler(commands=['search'])
        def handle_search(message):
            self._handle_search_command(message)

        @self.bot.message_handler(commands=['favorites'])
        def handle_favorites(message):
            self._handle_favorites_command(message)

        @self.bot.callback_query_handler(func=lambda call: True)
        def handle_callback(call):
            self._handle_callback_query(call)

        @self.bot.message_handler(content_types=['text'])
        def handle_text(message):
            self._handle_text_message(message)

    def _handle_callback_query(self, call: types.CallbackQuery) -> None:
        # Проверяем, что callback пришел от того же пользователя
        if call.from_user.id != call.message.chat.id:
            self.bot.answer_callback_query(call.id, "Действие недоступно", show_alert=True)
            return
        """Обработка всех callback-запросов от inline-кнопок"""
        try:
            user_id = call.from_user.id
            chat_id = call.message.chat.id
            data = call.data

            logger.info(f"Callback from {user_id}: {data}")

            # Удаляем клавиатуру у исходного сообщения
            try:
                self.bot.edit_message_reply_markup(
                    chat_id=chat_id,
                    message_id=call.message.message_id,
                    reply_markup=None
                )
            except Exception as e:
                logger.warning(f"Couldn't remove reply markup: {e}")

            # Обработка разных типов callback-запросов
            if data == 'search':
                self._handle_search_command(call.message)
            elif data == 'favorites':
                self._handle_favorites_command(call.message)
            elif data == 'next_match':
                self._show_next_match(call.message, user_id)
            elif data == 'add_favorite':
                self._add_current_match_to_favorites(call.message, user_id)
            elif data == 'add_blacklist':
                self._add_current_match_to_blacklist(call.message, user_id)
            elif data == 'back_to_menu':
                self._handle_start_command(call.message)
            else:
                logger.warning(f"Unknown callback data: {data}")
                self.bot.answer_callback_query(
                    call.id,
                    "Неизвестная команда",
                    show_alert=False
                )

            # Подтверждаем получение callback
            self.bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error handling callback: {e}")
            self.notifier.send_admin(f"Callback error: {e}\nData: {call.data}")
            try:
                self.bot.answer_callback_query(
                    call.id,
                    "⚠️ Произошла ошибка",
                    show_alert=True
                )
            except Exception as e:
                logger.error(f"Failed to answer callback: {e}")

    def _handle_start_command(self, message: types.Message):
        """Обработка команды /start"""
        try:
            user_id = message.from_user.id
            user = self.db.get_or_create_user(
                telegram_id=user_id,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name
            )

            self.user_states[user_id] = 'main_menu'

            welcome_text = (
                f"👋 Привет, {message.from_user.first_name}!\n\n"
                "Я бот VKinder - помогу найти интересных людей в VK.\n\n"
                "🔍 Используй /search для поиска\n"
                "❤️ /favorites - твои избранные анкеты\n"
                "❓ /help - справка по командам"
            )

            self.bot.send_message(
                message.chat.id,
                welcome_text,
                reply_markup=self._create_main_keyboard()
            )

        except Exception as e:
            logger.error(f"Ошибка в start команде: {e}")
            self._send_error_message(message.chat.id)

    def _handle_search_command(self, message: types.Message):
        """Обработка команды /search"""
        try:
            user_id = message.from_user.id
            user = self.db.get_user(user_id)

            if not user:
                self.bot.send_message(message.chat.id, "Сначала используйте /start")
                return

            if not user.vk_id:
                self.user_states[user_id] = 'waiting_vk_id'
                self.bot.send_message(
                    message.chat.id,
                    "🔗 Введите ваш VK ID или ссылку на профиль:"
                )
            else:
                self._request_age_range(message.chat.id, user_id)

        except Exception as e:
            logger.error(f"Ошибка в search команде: {e}")
            self._send_error_message(message.chat.id)

    def _show_next_match(self, message: types.Message, user_id: int) -> None:
        """Показывает следующую анкету в результатах поиска"""
        try:
            if user_id not in self.current_match_index:
                self.current_match_index[user_id] = 0
            else:
                self.current_match_index[user_id] += 1

            self._show_current_match(message.chat.id, user_id)
        except Exception as e:
            logger.error(f"Error showing next match: {e}")
            self.notifier.notify_error(message.chat.id, "search")

    def _add_current_match_to_favorites(self, message: types.Message, user_id: int) -> None:
        """Добавляет текущую анкету в избранное"""
        try:
            if user_id not in self.search_results or user_id not in self.current_match_index:
                self.notifier.notify_user(user_id, "Нет активных результатов поиска")
                return

            current_index = self.current_match_index[user_id]
            match = self.search_results[user_id][current_index]

            success = self.db.add_to_favorites(
                telegram_id=user_id,
                target_vk_id=match['id'],
                target_name=f"{match.get('first_name', '')} {match.get('last_name', '')}",
                target_link=f"https://vk.com/id{match['id']}"
            )

            if success:
                self.notifier.notify_user(user_id, "❤️ Анкета добавлена в избранное")
            else:
                self.notifier.notify_user(user_id, "ℹ️ Анкета уже в избранном")

            self._show_next_match(message, user_id)
        except Exception as e:
            logger.error(f"Error adding to favorites: {e}")
            self.notifier.notify_error(message.chat.id, "general")

    def _add_current_match_to_blacklist(self, message: types.Message, user_id: int) -> None:
        """Добавляет текущую анкету в черный список"""
        try:
            if user_id not in self.search_results or user_id not in self.current_match_index:
                self.notifier.notify_user(user_id, "Нет активных результатов поиска")
                return

            current_index = self.current_match_index[user_id]
            match = self.search_results[user_id][current_index]

            success = self.db.add_to_blacklist(
                telegram_id=user_id,
                blocked_vk_id=match['id']
            )

            if success:
                self.notifier.notify_user(user_id, "🚫 Анкета добавлена в черный список")
            else:
                self.notifier.notify_user(user_id, "ℹ️ Анкета уже в черном списке")

            self._show_next_match(message, user_id)
        except Exception as e:
            logger.error(f"Error adding to blacklist: {e}")
            self.notifier.notify_error(message.chat.id, "general")

    def _handle_favorites_command(self, message: types.Message):
        """Обработка команды /favorites"""
        try:
            favorites = self.db.get_favorites(message.from_user.id)

            if not favorites:
                self.bot.send_message(
                    message.chat.id,
                    "💔 У вас пока нет избранных анкет."
                )
                return

            favorites_text = "❤️ Ваши избранные анкеты:\n\n" + "\n".join(
                [f"{i + 1}. {fav['name']} - {fav['link']}"
                 for i, fav in enumerate(favorites)]
            )

            self.bot.send_message(
                message.chat.id,
                favorites_text,
                disable_web_page_preview=True
            )

        except Exception as e:
            logger.error(f"Ошибка в favorites команде: {e}")
            self._send_error_message(message.chat.id)

    def _handle_text_message(self, message: types.Message):
        """Обработка текстовых сообщений"""
        try:
            user_id = message.from_user.id
            current_state = self.user_states.get(user_id, 'main_menu')

            if current_state == 'waiting_vk_id':
                self._process_vk_id_input(message)
            elif current_state == 'waiting_age_from':
                self._process_age_input(message, 'from')
            elif current_state == 'waiting_age_to':
                self._process_age_input(message, 'to')
            else:
                self.bot.send_message(
                    message.chat.id,
                    "Я не понимаю эту команду. Используйте /help"
                )

        except Exception as e:
            logger.error(f"Ошибка обработки текста: {e}")
            self._send_error_message(message.chat.id)

    def _create_match_keyboard(self) -> types.InlineKeyboardMarkup:
        """Создает клавиатуру для управления анкетами"""
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton("❤️ В избранное", callback_data="add_favorite"),
            types.InlineKeyboardButton("🚫 Заблокировать", callback_data="add_blacklist"),
            types.InlineKeyboardButton("➡️ Следующая", callback_data="next_match"),
            types.InlineKeyboardButton("🏠 В меню", callback_data="back_to_menu")
        )
        return keyboard

    def _send_error_message(self, chat_id):
        """Отправляет сообщение об ошибке"""
        try:
            self.bot.send_message(
                chat_id,
                "⚠️ Произошла ошибка. Попробуйте позже."
            )
        except ApiTelegramException as e:
            logger.error(f"Не удалось отправить сообщение об ошибке: {e}")

    def run(self):
        """Запускает бота"""
        logger.info("Запуск бота...")
        try:
            self.bot.polling(none_stop=True, interval=1, timeout=60)
        except Exception as e:
            logger.critical(f"Бот остановлен с ошибкой: {e}")
            self.notifier.send_admin(f"Бот упал с ошибкой: {e}")
            raise


if __name__ == "__main__":
    try:
        bot = VKinderBot()
        bot.run()
    except Exception as e:
        logger.critical(f"Не удалось запустить бота: {e}")