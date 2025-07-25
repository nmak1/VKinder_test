import logging
import re

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
            self.temp_search_params: Dict[int, Dict] = {}

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
            elif data == 'help':
                help_text = (
                    "📖 <b>Справка по боту</b>\n\n"
                    "🔍 <b>Поиск</b> - найти анкеты по параметрам\n"
                    "❤️ <b>Избранное</b> - ваши сохраненные анкеты\n\n"
                    "При просмотре анкет:\n"
                    "❤️ - добавить в избранное\n"
                    "🚫 - добавить в черный список\n"
                    "➡️ - следующая анкета\n"
                    "🏠 - вернуться в меню"
                )
                self._send_message(
                    call.message.chat.id,
                    help_text
                )
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

    def _handle_start_command(self, message: types.Message) -> None:
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
                "Выбери действие:"
            )

            self.bot.send_message(
                chat_id=message.chat.id,
                text=welcome_text,
                reply_markup=self._create_main_keyboard(),
                parse_mode="HTML"
            )

            logger.info(f"User {user_id} started the bot")

        except Exception as e:
            logger.error(f"Error in start command: {e}")
            self.notifier.send_admin(f"Start command error: {e}")
            self._send_error_message(message.chat.id)

    def _handle_help_command(self, message: types.Message) -> None:
        """Обработка команды /help"""
        help_text = (
            "📖 <b>Справка по боту</b>\n\n"
            "🔍 <b>/search</b> - начать поиск анкет\n"
            "❤️ <b>/favorites</b> - посмотреть избранные анкеты\n"
            "🏠 <b>/start</b> - вернуться в главное меню\n\n"
            "После начала поиска вы сможете:\n"
            "• Добавлять анкеты в избранное ❤️\n"
            "• Добавлять в черный список 🚫\n"
            "• Просматривать следующие анкеты ➡️"
        )
        self._send_message(
            message.chat.id,
            help_text
        )

    def _handle_search_command(self, message: types.Message) -> None:
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
                    "🔗 Введите ваш VK ID или ссылку на профиль:",
                    reply_markup=self._create_cancel_keyboard()
                )
            else:
                self._request_age_range(message.chat.id, user_id)

        except Exception as e:
            logger.error(f"Ошибка в search команде: {e}")
            self._send_error_message(message.chat.id)

    def _process_vk_id_input(self, message: types.Message) -> None:
        """Обрабатывает ввод VK ID пользователем"""
        try:
            user_id = message.from_user.id
            text = message.text.strip()

            # Проверка на отмену
            if text.lower() == '❌ отмена':
                self.user_states[user_id] = 'main_menu'
                self._handle_start_command(message)
                return

            # Извлекаем VK ID из текста
            vk_id = self._extract_vk_id(text)

            if not vk_id:
                self.bot.send_message(
                    message.chat.id,
                    "❌ Неверный формат. Введите VK ID или ссылку на профиль:",
                    reply_markup=self._create_cancel_keyboard()
                )
                return

            # Получаем информацию о пользователе из VK
            user_info = self.vk_service.get_user_info(vk_id)
            if not user_info:
                self.bot.send_message(
                    message.chat.id,
                    "❌ Профиль не найден или закрыт. Попробуйте другой ID:",
                    reply_markup=self._create_cancel_keyboard()
                )
                return

            # Сохраняем информацию в базу данных
            age = self.vk_service.calculate_age_from_bdate(user_info.get('bdate'))
            gender = user_info.get('sex')
            city_id = user_info.get('city', {}).get('id')
            city_name = user_info.get('city', {}).get('title')

            success = self.db.update_user_vk_info(
                telegram_id=user_id,
                vk_id=vk_id,
                age=age,
                gender=gender,
                city_id=city_id,
                city_name=city_name
            )

            if success:
                self._request_age_range(message.chat.id, user_id)
            else:
                self._send_error_message(message.chat.id)

        except Exception as e:
            logger.error(f"Error processing VK ID: {e}")
            self._send_error_message(message.chat.id)

    def _extract_vk_id(self, text: str) -> Optional[int]:
        """Извлекает VK ID из строки (поддерживает разные форматы)"""
        # Если это просто число
        if text.isdigit():
            return int(text)

        # Если это ссылка на профиль
        patterns = [
            r'vk\.com/id(\d+)',
            r'vkontakte\.ru/id(\d+)',
            r'm\.vk\.com/id(\d+)',
            r'id(\d+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return int(match.group(1))

        return None

    def _request_age_range(self, chat_id: int, user_id: int) -> None:
        """Запрашивает возрастной диапазон для поиска"""
        try:
            self.user_states[user_id] = 'waiting_age_from'
            self.bot.send_message(
                chat_id,
                "🔢 Введите минимальный возраст для поиска (от 18 лет):",
                reply_markup=self._create_cancel_keyboard()
            )
        except Exception as e:
            logger.error(f"Error requesting age range: {e}")
            self._send_error_message(chat_id)

    def _process_age_input(self, message: types.Message, age_type: str) -> None:
        """Обрабатывает ввод возраста пользователем"""
        try:
            user_id = message.from_user.id
            text = message.text.strip()

            # Проверка на отмену
            if text.lower() == '❌ отмена':
                self.user_states[user_id] = 'main_menu'
                self._handle_start_command(message)
                return

            try:
                age = int(text)
                if age < 18 or age > 100:
                    raise ValueError
            except ValueError:
                self.bot.send_message(
                    message.chat.id,
                    "❌ Введите число от 18 до 100:",
                    reply_markup=self._create_cancel_keyboard()
                )
                return

            if age_type == 'from':
                self.temp_search_params[user_id] = {'age_from': age}
                self.user_states[user_id] = 'waiting_age_to'
                self.bot.send_message(
                    message.chat.id,
                    f"✅ Минимальный возраст: {age}\n\n"
                    f"Теперь введите максимальный возраст (не меньше {age}):",
                    reply_markup=self._create_cancel_keyboard()
                )
            else:
                if user_id not in self.temp_search_params:
                    self.temp_search_params[user_id] = {}

                age_from = self.temp_search_params[user_id].get('age_from', 18)
                if age < age_from:
                    self.bot.send_message(
                        message.chat.id,
                        f"❌ Максимальный возраст должен быть не меньше {age_from}:",
                        reply_markup=self._create_cancel_keyboard()
                    )
                    return

                self.temp_search_params[user_id]['age_to'] = age
                self._start_search(
                    message.chat.id,
                    user_id,
                    age_from,
                    age
                )

        except Exception as e:
            logger.error(f"Error processing age input: {e}")
            self._send_error_message(message.chat.id)

    def _start_search(self, chat_id: int, user_id: int, age_from: int, age_to: int) -> None:
        """Запускает поиск анкет по заданным параметрам"""
        try:
            user = self.db.get_user(user_id)
            if not user or not user.city_id or not user.gender:
                self._send_error_message(chat_id)
                return

            search_msg = self.bot.send_message(
                chat_id,
                f"🔍 Ищем анкеты в возрасте {age_from}-{age_to} лет..."
            )

            # Выполняем поиск
            results = self.search_service.find_matches(
                user_id=user_id,
                age_from=age_from,
                age_to=age_to
            )

            if not results:
                self.bot.edit_message_text(
                    "😔 Не найдено подходящих анкет. Попробуйте другие параметры.",
                    chat_id,
                    search_msg.message_id
                )
                return

            # Сохраняем результаты
            self.search_results[user_id] = results
            self.current_match_index[user_id] = 0
            self.user_states[user_id] = 'viewing_matches'

            # Удаляем сообщение о поиске
            self.bot.delete_message(chat_id, search_msg.message_id)

            # Показываем первую анкету
            self._show_current_match(chat_id, user_id)

        except Exception as e:
            logger.error(f"Error starting search: {e}")
            self._send_error_message(chat_id)
            self.notifier.send_admin(f"Search failed for {user_id}: {e}")

    def _show_current_match(self, chat_id: int, user_id: int) -> None:
        """Показывает текущую анкету"""
        try:
            if user_id not in self.search_results:
                self.bot.send_message(chat_id, "Нет результатов поиска. Используйте /search")
                return

            current_index = self.current_match_index.get(user_id, 0)
            results = self.search_results[user_id]

            if current_index >= len(results):
                self.bot.send_message(
                    chat_id,
                    "🎉 Вы просмотрели все анкеты!\nИспользуйте /search для нового поиска.",
                    reply_markup=self._create_main_keyboard()
                )
                return

            match = results[current_index]
            match_text = self._format_match_text(match, current_index, len(results))

            # Отправка фотографий (если есть)
            photos = self.search_service.get_match_photos(match['id'])
            if photos:
                media = []
                for i, photo in enumerate(photos[:3]):
                    if i == 0:
                        media.append(types.InputMediaPhoto(
                            photo['url'],
                            caption=match_text,
                            parse_mode="HTML"
                        ))
                    else:
                        media.append(types.InputMediaPhoto(photo['url']))

                self.bot.send_media_group(chat_id, media)
            else:
                self.bot.send_message(
                    chat_id,
                    match_text + "\n\n📷 Фотографии недоступны",
                    parse_mode="HTML"
                )

            # Отправка клавиатуры управления
            self.bot.send_message(
                chat_id,
                "Выберите действие:",
                reply_markup=self._create_match_keyboard()
            )

        except Exception as e:
            logger.error(f"Error showing match: {e}")
            self.notifier.send_admin(f"Show match error: {e}")
            self._send_error_message(chat_id)

    def _format_match_text(self, match: dict, current: int, total: int) -> str:
        """Форматирует текст для отображения анкеты"""
        name = f"{match.get('first_name', '')} {match.get('last_name', '')}"
        age = f", {match.get('age', '')} лет" if match.get('age') else ""
        city = f"\n🏙 {match.get('city', {}).get('title', '')}" if match.get('city') else ""

        return (
            f"👤 <b>{name}</b>{age}{city}\n"
            f"🔗 <a href='https://vk.com/id{match['id']}'>Профиль VK</a>\n\n"
            f"📊 Анкета {current + 1} из {total}"
        )

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

    def _handle_favorites_command(self, message: types.Message) -> None:
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
                [f"{i + 1}. <a href='{fav['link']}'>{fav['name']}</a>"
                 for i, fav in enumerate(favorites)]
            )

            self._send_message(
                message.chat.id,
                favorites_text
            )

        except Exception as e:
            logger.error(f"Ошибка в favorites команде: {e}")
            self._send_error_message(message.chat.id)

    def _handle_text_message(self, message: types.Message) -> None:
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

    def _create_main_keyboard(self) -> types.InlineKeyboardMarkup:
        """Создает основную клавиатуру главного меню"""
        keyboard = types.InlineKeyboardMarkup(row_width=2)

        buttons = [
            types.InlineKeyboardButton("🔍 Поиск", callback_data="search"),
            types.InlineKeyboardButton("❤️ Избранное", callback_data="favorites"),
            types.InlineKeyboardButton("ℹ️ Помощь", callback_data="help")
        ]

        keyboard.add(*buttons)
        return keyboard

    def _create_match_keyboard(self) -> types.InlineKeyboardMarkup:
        """Создает клавиатуру для управления анкетами"""
        keyboard = types.InlineKeyboardMarkup(row_width=2)

        buttons = [
            types.InlineKeyboardButton("❤️ В избранное", callback_data="add_favorite"),
            types.InlineKeyboardButton("🚫 В ч. список", callback_data="add_blacklist"),
            types.InlineKeyboardButton("➡️ Следующая", callback_data="next_match"),
            types.InlineKeyboardButton("🏠 В меню", callback_data="back_to_menu")
        ]

        keyboard.add(*buttons[:2])  # Первый ряд - 2 кнопки
        keyboard.add(buttons[2])  # Второй ряд - 1 кнопка
        keyboard.add(buttons[3])  # Третий ряд - 1 кнопка

        return keyboard

    def _create_cancel_keyboard(self) -> types.ReplyKeyboardMarkup:
        """Создает клавиатуру с кнопкой отмены"""
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(types.KeyboardButton("❌ Отмена"))
        return keyboard

    def _send_error_message(self, chat_id: int) -> None:
        """Отправляет сообщение об ошибке"""
        try:
            self.bot.send_message(
                chat_id,
                "⚠️ Произошла ошибка. Попробуйте позже."
            )
        except ApiTelegramException as e:
            logger.error(f"Не удалось отправить сообщение об ошибке: {e}")

    def _send_message(self, chat_id: int, text: str,
                      keyboard: Optional[types.ReplyKeyboardMarkup] = None,
                      parse_mode: Optional[str] = "HTML") -> None:
        """Универсальный метод отправки сообщений с обработкой ошибок"""
        try:
            self.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=keyboard,
                parse_mode=parse_mode,
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Failed to send message to {chat_id}: {e}")
            self.notifier.send_admin(f"Message send failed to {chat_id}: {e}")

    def run(self) -> None:
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