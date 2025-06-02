"""
Основной модуль Telegram бота VKinder.

Этот модуль содержит логику Telegram бота для поиска анкет в ВКонтакте.
Бот помогает пользователям находить потенциальных партнеров на основе
их предпочтений по возрасту, полу и местоположению.
"""

import telebot
from telebot import types
import logging
from typing import Dict, Any, List, Optional
import threading
import time

# Импортируем наши модули
from config import Config
from database import DatabaseManager, User
from vk_api_client import VKApiClient

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('vkinder_bot.log'),  # Логи в файл
        logging.StreamHandler()                   # Логи в консоль
    ]
)

logger = logging.getLogger(__name__)

def command_handler(command: str):
    """
    Декоратор для обработки команд бота.
    
    Args:
        command (str): Название команды
        
    Returns:
        function: Декорированная функция
    """
    def decorator(func):
        # Добавляем информацию о команде к функции
        func.command = command
        return func
    return decorator

def user_state_required(required_state: str = None):
    """
    Декоратор для проверки состояния пользователя.
    
    Args:
        required_state (str): Требуемое состояние пользователя
        
    Returns:
        function: Декорированная функция
    """
    def decorator(func):
        def wrapper(self, message, *args, **kwargs):
            # Получаем текущее состояние пользователя
            user_id = message.from_user.id
            current_state = self.user_states.get(user_id)
            
            # Проверяем соответствие состояния
            if required_state and current_state != required_state:
                self.bot.send_message(
                    message.chat.id,
                    "❌ Неверная команда в текущем состоянии. Используйте /start для начала."
                )
                return
            
            # Выполняем функцию, если состояние подходит
            return func(self, message, *args, **kwargs)
        return wrapper
    return decorator

class VKinderBot:
    """
    Основной класс Telegram бота VKinder.
    
    Обрабатывает сообщения пользователей, взаимодействует с API ВКонтакте
    и управляет базой данных для поиска потенциальных партнеров.
    
    Attributes:
        bot: Экземпляр Telegram бота
        db: Менеджер базы данных
        vk_client: Клиент API ВКонтакте
        user_states: Словарь состояний пользователей
        search_results: Кэш результатов поиска
        current_match_index: Индекс текущей анкеты для каждого пользователя
    """
    
    def __init__(self, telegram_token: str, vk_token: str, database_url: str):
        """
        Инициализация бота VKinder.
        
        Args:
            telegram_token (str): Токен Telegram бота
            vk_token (str): Токен API ВКонтакте
            database_url (str): URL базы данных
        """
        # Инициализируем Telegram бота
        self.bot = telebot.TeleBot(telegram_token)
        
        # Инициализируем менеджер базы данных
        self.db = DatabaseManager(database_url)
        
        # Создаем таблицы в базе данных
        self.db.create_tables()
        
        # Инициализируем клиент API ВКонтакте
        self.vk_client = VKApiClient(vk_token)
        
        # Словарь для хранения состояний пользователей
        # Ключ - ID пользователя, значение - текущее состояние
        self.user_states: Dict[int, str] = {}
        
        # Кэш результатов поиска для каждого пользователя
        # Ключ - ID пользователя, значение - список найденных анкет
        self.search_results: Dict[int, List[Dict[str, Any]]] = {}
        
        # Индекс текущей показываемой анкеты для каждого пользователя
        # Ключ - ID пользователя, значение - индекс в списке результатов
        self.current_match_index: Dict[int, int] = {}
        
        # Регистрируем обработчики команд и сообщений
        self._register_handlers()
        
        logger.info("VKinderBot инициализирован успешно")
    
    def _register_handlers(self) -> None:
        """
        Регистрирует обработчики команд и сообщений бота.
        """
        # Обработчик команды /start
        @self.bot.message_handler(commands=['start'])
        def handle_start(message):
            self.handle_start_command(message)
        
        # Обработчик команды /help
        @self.bot.message_handler(commands=['help'])
        def handle_help(message):
            self.handle_help_command(message)
        
        # Обработчик команды /search
        @self.bot.message_handler(commands=['search'])
        def handle_search(message):
            self.handle_search_command(message)
        
        # Обработчик команды /favorites
        @self.bot.message_handler(commands=['favorites'])
        def handle_favorites(message):
            self.handle_favorites_command(message)
        
        # Обработчик callback-запросов (нажатий на inline кнопки)
        @self.bot.callback_query_handler(func=lambda call: True)
        def handle_callback(call):
            self.handle_callback_query(call)
        
        # Обработчик текстовых сообщений
        @self.bot.message_handler(content_types=['text'])
        def handle_text(message):
            self.handle_text_message(message)
        
        logger.info("Обработчики команд зарегистрированы")
    
    @command_handler('start')
    def handle_start_command(self, message: types.Message) -> None:
        """
        Обрабатывает команду /start.
        
        Args:
            message (types.Message): Сообщение от пользователя
        """
        # Получаем информацию о пользователе из Telegram
        user_id = message.from_user.id
        first_name = message.from_user.first_name or "Пользователь"
        last_name = message.from_user.last_name
        
        # Создаем или обновляем пользователя в базе данных
        user = self.db.get_or_create_user(user_id, first_name, last_name)
        
        # Сбрасываем состояние пользователя
        self.user_states[user_id] = 'main_menu'
        
        # Создаем приветственное сообщение
        welcome_text = (
            f"👋 Привет, {first_name}!\n\n"
            "Я бот VKinder - помогу тебе найти интересных людей в ВКонтакте! 💕\n\n"
            "🔍 Для начала поиска нажми кнопку ниже или используй команду /search\n"
            "❤️ Просмотреть избранное: /favorites\n"
            "❓ Помощь: /help"
        )
        
        # Создаем клавиатуру с основными действиями
        keyboard = self._create_main_keyboard()
        
        # Отправляем приветственное сообщение
        self.bot.send_message(
            message.chat.id,
            welcome_text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        logger.info(f"Пользователь {user_id} ({first_name}) начал работу с ботом")
    
    @command_handler('help')
    def handle_help_command(self, message: types.Message) -> None:
        """
        Обрабатывает команду /help.
        
        Args:
            message (types.Message): Сообщение от пользователя
        """
        help_text = (
            "📖 <b>Справка по использованию VKinder</b>\n\n"
            "🔍 <b>/search</b> - начать поиск анкет\n"
            "❤️ <b>/favorites</b> - посмотреть избранные анкеты\n"
            "🏠 <b>/start</b> - вернуться в главное меню\n"
            "❓ <b>/help</b> - показать эту справку\n\n"
            "<b>Как пользоваться:</b>\n"
            "1️⃣ Введи свой ID ВКонтакте\n"
            "2️⃣ Укажи возрастной диапазон для поиска\n"
            "3️⃣ Просматривай анкеты и добавляй понравившиеся в избранное\n\n"
            "💡 <b>Совет:</b> Убедись, что твой профиль ВКонтакте открыт для поиска!"
        )
        
        self.bot.send_message(
            message.chat.id,
            help_text,
            parse_mode='HTML'
        )
        
        logger.info(f"Пользователь {message.from_user.id} запросил справку")
    
    @command_handler('search')
    def handle_search_command(self, message: types.Message) -> None:
        """
        Обрабатывает команду /search.
        
        Args:
            message (types.Message): Сообщение от пользователя
        """
        user_id = message.from_user.id
        
        # Получаем пользователя из базы данных
        user = self.db.get_user_by_telegram_id(user_id)
        
        if not user:
            self.bot.send_message(
                message.chat.id,
                "❌ Ошибка: пользователь не найден. Используйте /start"
            )
            return
        
        # Проверяем, есть ли информация о ВКонтакте
        if not user.vk_id:
            # Запрашиваем ID ВКонтакте
            self.user_states[user_id] = 'waiting_vk_id'
            self.bot.send_message(
                message.chat.id,
                "🔗 Для поиска анкет мне нужен твой ID ВКонтакте.\n\n"
                "📝 Введи свой ID (например: 123456789) или ссылку на профиль:"
            )
        else:
            # Если ID уже есть, запрашиваем возрастной диапазон
            self._request_age_range(message.chat.id, user_id)
        
        logger.info(f"Пользователь {user_id} начал поиск")
    
    @command_handler('favorites')
    def handle_favorites_command(self, message: types.Message) -> None:
        """
        Обрабатывает команду /favorites.
        
        Args:
            message (types.Message): Сообщение от пользователя
        """
        user_id = message.from_user.id
        
        # Получаем список избранных анкет
        favorites = self.db.get_favorites(user_id)
        
        if not favorites:
            # Если избранных нет
            self.bot.send_message(
                message.chat.id,
                "💔 У тебя пока нет избранных анкет.\n\n"
                "Начни поиск с помощью /search и добавляй понравившиеся профили!"
            )
            return
        
        # Формируем сообщение со списком избранных
        favorites_text = "❤️ <b>Твои избранные анкеты:</b>\n\n"
        
        for i, favorite in enumerate(favorites, 1):
            favorites_text += (
                f"{i}. <a href='{favorite['link']}'>{favorite['name']}</a>\n"
                f"📅 Добавлено: {favorite['added_at'].strftime('%d.%m.%Y')}\n\n"
            )
        
        # Отправляем список избранных
        self.bot.send_message(
            message.chat.id,
            favorites_text,
            parse_mode='HTML',
            disable_web_page_preview=True
        )
        
        logger.info(f"Пользователь {user_id} просмотрел избранное ({len(favorites)} анкет)")
    
    def handle_callback_query(self, call: types.CallbackQuery) -> None:
        """
        Обрабатывает callback-запросы от inline кнопок.
        
        Args:
            call (types.CallbackQuery): Callback-запрос
        """
        user_id = call.from_user.id
        data = call.data
        
        try:
            # Обрабатываем различные типы callback-запросов
            if data == 'start_search':
                # Начать поиск
                self.handle_search_command(call.message)
            
            elif data == 'show_favorites':
                # Показать избранное
                self.handle_favorites_command(call.message)
            
            elif data == 'add_favorite':
                # Добавить в избранное
                self._add_current_match_to_favorites(call.message, user_id)
            
            elif data == 'add_blacklist':
                # Добавить в черный список
                self._add_current_match_to_blacklist(call.message, user_id)
            
            elif data == 'next_match':
                # Следующая анкета
                self._show_next_match(call.message, user_id)
            
            elif data == 'back_to_menu':
                # Вернуться в главное меню
                self.handle_start_command(call.message)
            
            # Подтверждаем обработку callback-запроса
            self.bot.answer_callback_query(call.id)
            
        except Exception as e:
            logger.error(f"Ошибка при обработке callback {data} от пользователя {user_id}: {e}")
            self.bot.answer_callback_query(call.id, "❌ Произошла ошибка")
    
    @user_state_required()
    def handle_text_message(self, message: types.Message) -> None:
        """
        Обрабатывает текстовые сообщения в зависимости от состояния пользователя.
        
        Args:
            message (types.Message): Текстовое сообщение
        """
        user_id = message.from_user.id
        text = message.text.strip()
        current_state = self.user_states.get(user_id, 'main_menu')
        
        # Обрабатываем сообщение в зависимости от состояния
        if current_state == 'waiting_vk_id':
            self._process_vk_id_input(message, text)
        
        elif current_state == 'waiting_age_from':
            self._process_age_from_input(message, text)
        
        elif current_state == 'waiting_age_to':
            self._process_age_to_input(message, text)
        
        else:
            # Если состояние неизвестно, предлагаем использовать команды
            self.bot.send_message(
                message.chat.id,
                "🤔 Я не понимаю. Используй команды:\n"
                "/start - главное меню\n"
                "/search - поиск анкет\n"
                "/favorites - избранное\n"
                "/help - справка"
            )
    
    def _process_vk_id_input(self, message: types.Message, text: str) -> None:
        """
        Обрабатывает ввод ID ВКонтакте.
        
        Args:
            message (types.Message): Сообщение пользователя
            text (str): Введенный текст
        """
        user_id = message.from_user.id
        
        # Извлекаем ID из текста (может быть ссылкой или числом)
        vk_id = self._extract_vk_id(text)
        
        if not vk_id:
            self.bot.send_message(
                message.chat.id,
                "❌ Неверный формат ID ВКонтакте.\n\n"
                "Введи число (например: 123456789) или ссылку на профиль:"
            )
            return
        
        # Получаем информацию о пользователе ВКонтакте
        vk_user_info = self.vk_client.get_user_info(vk_id)
        
        if not vk_user_info:
            self.bot.send_message(
                message.chat.id,
                "❌ Пользователь ВКонтакте не найден или профиль закрыт.\n\n"
                "Проверь ID и убедись, что профиль открыт для поиска:"
            )
            return
        
        # Извлекаем информацию о пользователе
        age = None
        if 'bdate' in vk_user_info:
            age = self.vk_client.calculate_age_from_bdate(vk_user_info['bdate'])
        
        gender = vk_user_info.get('sex')
        city_id = None
        city_name = None
        
        if 'city' in vk_user_info:
            city_id = vk_user_info['city']['id']
            city_name = vk_user_info['city']['title']
        
        # Обновляем информацию пользователя в базе данных
        success = self.db.update_user_vk_info(
            user_id, vk_id, age, gender, city_id, city_name
        )
        
        if success:
            # Формируем сообщение с информацией о пользователе
            user_name = f"{vk_user_info.get('first_name', '')} {vk_user_info.get('last_name', '')}"
            info_text = f"✅ Профиль найден: {user_name}\n"
            
            if age:
                info_text += f"🎂 Возраст: {age} лет\n"
            if city_name:
                info_text += f"🏙 Город: {city_name}\n"
            
            self.bot.send_message(message.chat.id, info_text)
            
            # Переходим к запросу возрастного диапазона
            self._request_age_range(message.chat.id, user_id)
        else:
            self.bot.send_message(
                message.chat.id,
                "❌ Ошибка при сохранении данных. Попробуй еще раз."
            )
        
        logger.info(f"Пользователь {user_id} добавил VK ID: {vk_id}")
    
    def _process_age_from_input(self, message: types.Message, text: str) -> None:
        """
        Обрабатывает ввод минимального возраста.
        
        Args:
            message (types.Message): Сообщение пользователя
            text (str): Введенный текст
        """
        user_id = message.from_user.id
        
        try:
            # Пытаемся преобразовать в число
            age_from = int(text)
            
            # Проверяем корректность возраста
            if age_from < 18:
                self.bot.send_message(
                    message.chat.id,
                    "❌ Минимальный возраст должен быть не менее 18 лет.\n"
                    "Введи минимальный возраст:"
                )
                return
            
            if age_from > 100:
                self.bot.send_message(
                    message.chat.id,
                    "❌ Возраст не может быть больше 100 лет.\n"
                    "Введи минимальный возраст:"
                )
                return
            
            # Сохраняем минимальный возраст во временном хранилище
            if not hasattr(self, 'temp_search_params'):
                self.temp_search_params = {}
            
            if user_id not in self.temp_search_params:
                self.temp_search_params[user_id] = {}
            
            self.temp_search_params[user_id]['age_from'] = age_from
            
            # Переходим к запросу максимального возраста
            self.user_states[user_id] = 'waiting_age_to'
            self.bot.send_message(
                message.chat.id,
                f"✅ Минимальный возраст: {age_from}\n\n"
                f"Теперь введи максимальный возраст (больше {age_from}):"
            )
            
        except ValueError:
            self.bot.send_message(
                message.chat.id,
                "❌ Введи число.\nМинимальный возраст для поиска:"
            )
    
    def _process_age_to_input(self, message: types.Message, text: str) -> None:
        """
        Обрабатывает ввод максимального возраста и запускает поиск.
        
        Args:
            message (types.Message): Сообщение пользователя
            text (str): Введенный текст
        """
        user_id = message.from_user.id
        
        try:
            # Пытаемся преобразовать в число
            age_to = int(text)
            
            # Получаем минимальный возраст из временного хранилища
            age_from = self.temp_search_params.get(user_id, {}).get('age_from', 18)
            
            # Проверяем корректность возраста
            if age_to <= age_from:
                self.bot.send_message(
                    message.chat.id,
                    f"❌ Максимальный возраст должен быть больше {age_from}.\n"
                    f"Введи максимальный возраст:"
                )
                return
            
            if age_to > 100:
                self.bot.send_message(
                    message.chat.id,
                    "❌ Возраст не может быть больше 100 лет.\n"
                    "Введи максимальный возраст:"
                )
                return
            
            # Сохраняем максимальный возраст
            self.temp_search_params[user_id]['age_to'] = age_to
            
            # Запускаем поиск
            self._start_search(message.chat.id, user_id, age_from, age_to)
            
        except ValueError:
            self.bot.send_message(
                message.chat.id,
                "❌ Введи число.\nМаксимальный возраст для поиска:"
            )
    
    def _request_age_range(self, chat_id: int, user_id: int) -> None:
        """
        Запрашивает возрастной диапазон для поиска.
        
        Args:
            chat_id (int): ID чата
            user_id (int): ID пользователя
        """
        self.user_states[user_id] = 'waiting_age_from'
        self.bot.send_message(
            chat_id,
            "🎯 Теперь укажи возрастной диапазон для поиска.\n\n"
            "Введи минимальный возраст (от 18 лет):"
        )
    
    def _start_search(self, chat_id: int, user_id: int, age_from: int, age_to: int) -> None:
        """
        Запускает поиск анкет по заданным параметрам.
        
        Args:
            chat_id (int): ID чата
            user_id (int): ID пользователя
            age_from (int): Минимальный возраст
            age_to (int): Максимальный возраст
        """
        # Получаем информацию о пользователе из базы данных
        user = self.db.get_user_by_telegram_id(user_id)
        
        if not user or not user.vk_id or not user.gender or not user.city_id:
            self.bot.send_message(
                chat_id,
                "❌ Недостаточно данных для поиска. Используй /search для повторной настройки."
            )
            return
        
        # Отправляем сообщение о начале поиска
        search_message = self.bot.send_message(
            chat_id,
            "🔍 Ищу подходящие анкеты...\n"
            f"Параметры: {age_from}-{age_to} лет, {user.city_name}"
        )
        
        try:
            # Выполняем поиск через API ВКонтакте
            search_results = self.vk_client.search_users(
                age_from=age_from,
                age_to=age_to,
                sex=user.gender,
                city_id=user.city_id,
                count=50
            )
            
            # Фильтруем результаты (исключаем заблокированных пользователей)
            filtered_results = []
            for result in search_results:
                if not self.db.is_in_blacklist(user_id, result['id']):
                    filtered_results.append(result)
            
            if not filtered_results:
                self.bot.edit_message_text(
                    "😔 К сожалению, не найдено подходящих анкет.\n\n"
                    "Попробуй изменить параметры поиска или повторить позже.",
                    chat_id,
                    search_message.message_id
                )
                self.user_states[user_id] = 'main_menu'
                return
            
            # Сохраняем результаты поиска
            self.search_results[user_id] = filtered_results
            self.current_match_index[user_id] = 0
            
            # Удаляем сообщение о поиске
            self.bot.delete_message(chat_id, search_message.message_id)
            
            # Показываем первую анкету
            self._show_current_match(chat_id, user_id)
            
            # Обновляем состояние пользователя
            self.user_states[user_id] = 'viewing_matches'
            
            logger.info(f"Найдено {len(filtered_results)} анкет для пользователя {user_id}")
            
        except Exception as e:
            logger.error(f"Ошибка при поиске для пользователя {user_id}: {e}")
            self.bot.edit_message_text(
                "❌ Произошла ошибка при поиске. Попробуй позже.",
                chat_id,
                search_message.message_id
            )
            self.user_states[user_id] = 'main_menu'
    
    def _show_current_match(self, chat_id: int, user_id: int) -> None:
        """
        Показывает текущую анкету пользователю.
        
        Args:
            chat_id (int): ID чата
            user_id (int): ID пользователя
        """
        # Проверяем наличие результатов поиска
        if user_id not in self.search_results or not self.search_results[user_id]:
            self.bot.send_message(
                chat_id,
                "❌ Нет результатов поиска. Используй /search для нового поиска."
            )
            return
        
        # Получаем текущий индекс
        current_index = self.current_match_index.get(user_id, 0)
        results = self.search_results[user_id]
        
        # Проверяем, не закончились ли анкеты
        if current_index >= len(results):
            self.bot.send_message(
                chat_id,
                "🎉 Ты просмотрел все найденные анкеты!\n\n"
                "Используй /search для нового поиска.",
                reply_markup=self._create_main_keyboard()
            )
            self.user_states[user_id] = 'main_menu'
            return
        
        # Получаем текущую анкету
        current_match = results[current_index]
        match_vk_id = current_match['id']
        
        # Получаем фотографии пользователя
        photos = self.vk_client.get_user_photos(match_vk_id, count=3)
        
        # Формируем информацию об анкете
        first_name = current_match.get('first_name', 'Имя скрыто')
        last_name = current_match.get('last_name', '')
        full_name = f"{first_name} {last_name}".strip()
        
        # Вычисляем возраст, если есть дата рождения
        age_text = ""
        if 'bdate' in current_match:
            age = self.vk_client.calculate_age_from_bdate(current_match['bdate'])
            if age:
                age_text = f", {age} лет"
        
        # Формируем текст сообщения
        match_text = (
            f"👤 <b>{full_name}</b>{age_text}\n"
            f"🔗 <a href='https://vk.com/id{match_vk_id}'>Профиль ВКонтакте</a>\n\n"
            f"📊 Анкета {current_index + 1} из {len(results)}"
        )
        
        # Создаем клавиатуру для взаимодействия с анкетой
        keyboard = self._create_match_keyboard()
        
        if photos:
            # Если есть фотографии, отправляем их группой
            media_group = []
            for i, photo in enumerate(photos[:3]):  # Максимум 3 фотографии
                if i == 0:
                    # К первой фотографии добавляем описание
                    media_group.append(
                        types.InputMediaPhoto(
                            photo['url'],
                            caption=match_text,
                            parse_mode='HTML'
                        )
                    )
                else:
                    media_group.append(types.InputMediaPhoto(photo['url']))
            
            # Отправляем группу фотографий
            self.bot.send_media_group(chat_id, media_group)
            
            # Отправляем клавиатуру отдельным сообщением
            self.bot.send_message(
                chat_id,
                "Выбери действие:",
                reply_markup=keyboard
            )
        else:
            # Если фотографий нет, отправляем только текст
            self.bot.send_message(
                chat_id,
                match_text + "\n\n📷 Фотографии недоступны",
                reply_markup=keyboard,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
        
        logger.info(f"Показана анкета {current_index + 1}/{len(results)} пользователю {user_id}")
    
    def _show_next_match(self, message: types.Message, user_id: int) -> None:
        """
        Показывает следующую анкету.
        
        Args:
            message (types.Message): Сообщение пользователя
            user_id (int): ID пользователя
        """
        # Увеличиваем индекс текущей анкеты
        if user_id in self.current_match_index:
            self.current_match_index[user_id] += 1
        
        # Показываем следующую анкету
        self._show_current_match(message.chat.id, user_id)
    
    def _add_current_match_to_favorites(self, message: types.Message, user_id: int) -> None:
        """
        Добавляет текущую анкету в избранное.
        
        Args:
            message (types.Message): Сообщение пользователя
            user_id (int): ID пользователя
        """
        # Проверяем наличие текущей анкеты
        if (user_id not in self.search_results or 
            user_id not in self.current_match_index or
            not self.search_results[user_id]):
            self.bot.send_message(
                message.chat.id,
                "❌ Нет активной анкеты для добавления в избранное."
            )
            return
        
        # Получаем текущую анкету
        current_index = self.current_match_index[user_id]
        results = self.search_results[user_id]
        
        if current_index >= len(results):
            self.bot.send_message(
                message.chat.id,
                "❌ Нет активной анкеты для добавления в избранное."
            )
            return
        
        current_match = results[current_index]
        match_vk_id = current_match['id']
        
        # Формируем имя и ссылку
        first_name = current_match.get('first_name', 'Имя скрыто')
        last_name = current_match.get('last_name', '')
        full_name = f"{first_name} {last_name}".strip()
        profile_link = f"https://vk.com/id{match_vk_id}"
        
        # Добавляем в избранное
        success = self.db.add_to_favorites(user_id, match_vk_id, full_name, profile_link)
        
        if success:
            self.bot.send_message(
                message.chat.id,
                f"❤️ {full_name} добавлен в избранное!"
            )
            logger.info(f"Пользователь {user_id} добавил в избранное: {full_name}")
        else:
            self.bot.send_message(
                message.chat.id,
                f"ℹ️ {full_name} уже в твоем избранном."
            )
        
        # Показываем следующую анкету
        self._show_next_match(message, user_id)
    
    def _add_current_match_to_blacklist(self, message: types.Message, user_id: int) -> None:
        """
        Добавляет текущую анкету в черный список.
        
        Args:
            message (types.Message): Сообщение пользователя
            user_id (int): ID пользователя
        """
        # Проверяем наличие текущей анкеты
        if (user_id not in self.search_results or 
            user_id not in self.current_match_index or
            not self.search_results[user_id]):
            self.bot.send_message(
                message.chat.id,
                "❌ Нет активной анкеты для добавления в черный список."
            )
            return
        
        # Получаем текущую анкету
        current_index = self.current_match_index[user_id]
        results = self.search_results[user_id]
        
        if current_index >= len(results):
            self.bot.send_message(
                message.chat.id,
                "❌ Нет активной анкеты для добавления в черный список."
            )
            return
        
        current_match = results[current_index]
        match_vk_id = current_match['id']
        
        # Добавляем в черный список
        success = self.db.add_to_blacklist(user_id, match_vk_id)
        
        if success:
            self.bot.send_message(
                message.chat.id,
                "🚫 Анкета добавлена в черный список и больше не будет показываться."
            )
            logger.info(f"Пользователь {user_id} добавил в черный список: {match_vk_id}")
        else:
            self.bot.send_message(
                message.chat.id,
                "ℹ️ Эта анкета уже в черном списке."
            )
        
        # Показываем следующую анкету
        self._show_next_match(message, user_id)
    
    def _create_main_keyboard(self) -> types.InlineKeyboardMarkup:
        """
        Создает основную клавиатуру бота.
        
        Returns:
            types.InlineKeyboardMarkup: Клавиатура с основными действиями
        """
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        
        # Кнопки основного меню
        search_btn = types.InlineKeyboardButton("🔍 Поиск", callback_data="start_search")
        favorites_btn = types.InlineKeyboardButton("❤️ Избранное", callback_data="show_favorites")
        
        keyboard.add(search_btn, favorites_btn)
        
        return keyboard
    
    def _create_match_keyboard(self) -> types.InlineKeyboardMarkup:
        """
        Создает клавиатуру для взаимодействия с анкетой.
        
        Returns:
            types.InlineKeyboardMarkup: Клавиатура для действий с анкетой
        """
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        
        # Кнопки для действий с анкетой
        favorite_btn = types.InlineKeyboardButton("❤️ В избранное", callback_data="add_favorite")
        blacklist_btn = types.InlineKeyboardButton("🚫 Заблокировать", callback_data="add_blacklist")
        next_btn = types.InlineKeyboardButton("➡️ Следующая", callback_data="next_match")
        menu_btn = types.InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")
        
        keyboard.add(favorite_btn, blacklist_btn)
        keyboard.add(next_btn)
        keyboard.add(menu_btn)
        
        return keyboard
    
    def _extract_vk_id(self, text: str) -> Optional[int]:
        """
        Извлекает ID ВКонтакте из текста (ссылки или числа).
        
        Args:
            text (str): Текст для обработки
            
        Returns:
            Optional[int]: ID ВКонтакте или None
        """
        import re
        
        # Удаляем пробелы
        text = text.strip()
        
        # Если это просто число
        if text.isdigit():
            return int(text)
        
        # Паттерны для извлечения ID из ссылок ВКонтакте
        patterns = [
            r'vk\.com/id(\d+)',           # https://vk.com/id123456
            r'vkontakte\.ru/id(\d+)',     # https://vkontakte.ru/id123456
            r'm\.vk\.com/id(\d+)',        # https://m.vk.com/id123456
            r'id(\d+)',                   # id123456
        ]
        
        # Пробуем каждый паттерн
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return int(match.group(1))
        
        return None
    
    def run(self) -> None:
        """
        Запускает бота в режиме polling.
        """
        logger.info("Запуск VKinder бота...")
        
        try:
            # Запускаем бота с обработкой исключений
            self.bot.polling(none_stop=True, interval=1, timeout=60)
        except Exception as e:
            logger.error(f"Критическая ошибка бота: {e}")
            raise

def main():
    """
    Основная функция для запуска бота.
    """
    try:
        # Проверяем конфигурацию
        Config.validate()
        
        # Создаем экземпляр бота
        bot = VKinderBot(
            telegram_token=Config.TELEGRAM_TOKEN,
            vk_token=Config.VK_TOKEN,
            database_url=Config.DATABASE_URL
        )
        
        # Запускаем бота
        bot.run()
        
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        raise

if __name__ == "__main__":
    main()
