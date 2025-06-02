"""
Модуль для работы с API ВКонтакте.

Этот модуль содержит класс VKApiClient для взаимодействия с API ВКонтакте,
включая поиск пользователей, получение информации о профилях и фотографиях.
"""

import requests
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

# Настраиваем логирование для отслеживания запросов к API
logger = logging.getLogger(__name__)

def retry_on_error(max_retries: int = 3, delay: float = 1.0):
    """
    Декоратор для повторного выполнения функции при ошибке.
    
    Args:
        max_retries (int): Максимальное количество попыток
        delay (float): Задержка между попытками в секундах
        
    Returns:
        function: Декорированная функция
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Перебираем попытки выполнения функции
            for attempt in range(max_retries):
                try:
                    # Пытаемся выполнить функцию
                    return func(*args, **kwargs)
                except Exception as e:
                    # Логируем ошибку
                    logger.warning(f"Попытка {attempt + 1} не удалась: {e}")
                    
                    # Если это не последняя попытка, ждем и пробуем снова
                    if attempt < max_retries - 1:
                        time.sleep(delay)
                    else:
                        # Если все попытки исчерпаны, поднимаем исключение
                        logger.error(f"Все {max_retries} попыток исчерпаны для {func.__name__}")
                        raise
        return wrapper
    return decorator

def rate_limit(calls_per_second: float = 3.0):
    """
    Декоратор для ограничения частоты вызовов функции.
    
    Args:
        calls_per_second (float): Максимальное количество вызовов в секунду
        
    Returns:
        function: Декорированная функция
    """
    # Вычисляем минимальный интервал между вызовами
    min_interval = 1.0 / calls_per_second
    
    def decorator(func):
        # Время последнего вызова функции
        last_called = [0.0]
        
        def wrapper(*args, **kwargs):
            # Вычисляем время, прошедшее с последнего вызова
            elapsed = time.time() - last_called[0]
            
            # Если прошло недостаточно времени, ждем
            if elapsed < min_interval:
                sleep_time = min_interval - elapsed
                time.sleep(sleep_time)
            
            # Обновляем время последнего вызова
            last_called[0] = time.time()
            
            # Выполняем функцию
            return func(*args, **kwargs)
        return wrapper
    return decorator

class VKApiClient:
    """
    Клиент для работы с API ВКонтакте.
    
    Предоставляет методы для поиска пользователей, получения информации
    о профилях и фотографиях через официальное API ВКонтакте.
    
    Attributes:
        token (str): Токен доступа к API ВКонтакте
        version (str): Версия API ВКонтакте
        base_url (str): Базовый URL для запросов к API
    """
    
    def __init__(self, token: str, version: str = '5.131'):
        """
        Инициализация клиента API ВКонтакте.
        
        Args:
            token (str): Токен доступа к API ВКонтакте
            version (str): Версия API ВКонтакте
        """
        # Сохраняем токен доступа
        self.token = token
        
        # Сохраняем версию API
        self.version = version
        
        # Базовый URL для всех запросов к API ВКонтакте
        self.base_url = 'https://api.vk.com/method/'
        
        # Логируем успешную инициализацию
        logger.info("VKApiClient инициализирован")
    
    @rate_limit(calls_per_second=3.0)
    @retry_on_error(max_retries=3, delay=1.0)
    def _make_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Выполняет запрос к API ВКонтакте.
        
        Args:
            method (str): Название метода API
            params (Dict[str, Any]): Параметры запроса
            
        Returns:
            Dict[str, Any]: Ответ от API
            
        Raises:
            Exception: При ошибке запроса к API
        """
        # Добавляем обязательные параметры к запросу
        params.update({
            'access_token': self.token,  # Токен доступа
            'v': self.version            # Версия API
        })
        
        # Формируем полный URL для запроса
        url = f"{self.base_url}{method}"
        
        # Логируем запрос (без токена для безопасности)
        safe_params = {k: v for k, v in params.items() if k != 'access_token'}
        logger.debug(f"Запрос к {method} с параметрами: {safe_params}")
        
        # Выполняем HTTP GET запрос
        response = requests.get(url, params=params, timeout=10)
        
        # Проверяем статус ответа
        response.raise_for_status()
        
        # Парсим JSON ответ
        data = response.json()
        
        # Проверяем наличие ошибок в ответе API
        if 'error' in data:
            error_code = data['error'].get('error_code', 0)
            error_msg = data['error'].get('error_msg', 'Неизвестная ошибка')
            
            # Обрабатываем специфичные ошибки API
            if error_code == 6:  # Too many requests per second
                logger.warning("Превышен лимит запросов, ожидание...")
                time.sleep(1)
                raise Exception(f"Rate limit exceeded: {error_msg}")
            elif error_code == 5:  # User authorization failed
                raise Exception(f"Ошибка авторизации: {error_msg}")
            else:
                raise Exception(f"Ошибка API ВКонтакте ({error_code}): {error_msg}")
        
        # Возвращаем данные из ответа
        return data.get('response', {})
    
    def get_user_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Получает информацию о пользователе ВКонтакте.
        
        Args:
            user_id (int): ID пользователя ВКонтакте
            
        Returns:
            Optional[Dict[str, Any]]: Информация о пользователе или None
        """
        try:
            # Параметры запроса для получения информации о пользователе
            params = {
                'user_ids': str(user_id),  # ID пользователя (строка)
                'fields': 'sex,bdate,city,photo_max_orig'  # Запрашиваемые поля
            }
            
            # Выполняем запрос к методу users.get
            response = self._make_request('users.get', params)
            
            # Проверяем, есть ли данные в ответе
            if response and len(response) > 0:
                user_data = response[0]
                logger.info(f"Получена информация о пользователе {user_id}")
                return user_data
            else:
                logger.warning(f"Пользователь {user_id} не найден")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка при получении информации о пользователе {user_id}: {e}")
            return None
    
    def search_users(self, age_from: int, age_to: int, sex: int, 
                    city_id: int, count: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Ищет пользователей по заданным критериям.
        
        Args:
            age_from (int): Минимальный возраст
            age_to (int): Максимальный возраст
            sex (int): Пол (1 - женский, 2 - мужской)
            city_id (int): ID города
            count (int): Количество результатов (максимум 1000)
            offset (int): Смещение для пагинации
            
        Returns:
            List[Dict[str, Any]]: Список найденных пользователей
        """
        try:
            # Параметры поиска пользователей
            params = {
                'count': min(count, 1000),  # Ограничиваем максимальным значением API
                'offset': offset,           # Смещение для пагинации
                'age_from': age_from,       # Минимальный возраст
                'age_to': age_to,          # Максимальный возраст
                'sex': 3 - sex,            # Инвертируем пол (ищем противоположный)
                'city': city_id,           # ID города
                'status': 6,               # Статус "в активном поиске"
                'has_photo': 1,            # Только с фотографиями
                'fields': 'photo_max_orig,city,bdate'  # Дополнительные поля
            }
            
            # Выполняем запрос к методу users.search
            response = self._make_request('users.search', params)
            
            # Извлекаем список пользователей из ответа
            users = response.get('items', [])
            
            logger.info(f"Найдено {len(users)} пользователей по критериям поиска")
            return users
            
        except Exception as e:
            logger.error(f"Ошибка при поиске пользователей: {e}")
            return []
    
    def get_user_photos(self, user_id: int, count: int = 10) -> List[Dict[str, Any]]:
        """
        Получает фотографии пользователя, отсортированные по популярности.
        
        Args:
            user_id (int): ID пользователя ВКонтакте
            count (int): Количество фотографий для получения
            
        Returns:
            List[Dict[str, Any]]: Список фотографий с информацией о лайках
        """
        try:
            # Параметры запроса фотографий профиля
            params = {
                'owner_id': user_id,     # ID владельца фотографий
                'album_id': 'profile',   # Альбом "Фотографии профиля"
                'extended': 1,           # Расширенная информация (включая лайки)
                'count': count           # Количество фотографий
            }
            
            # Выполняем запрос к методу photos.get
            response = self._make_request('photos.get', params)
            
            # Извлекаем список фотографий
            photos = response.get('items', [])
            
            # Обрабатываем каждую фотографию
            processed_photos = []
            for photo in photos:
                # Находим URL фотографии наибольшего размера
                max_size_url = self._get_max_size_photo_url(photo.get('sizes', []))
                
                if max_size_url:
                    processed_photos.append({
                        'id': photo['id'],                    # ID фотографии
                        'owner_id': photo['owner_id'],        # ID владельца
                        'url': max_size_url,                  # URL фотографии
                        'likes': photo.get('likes', {}).get('count', 0),  # Количество лайков
                        'date': photo.get('date', 0)          # Дата загрузки
                    })
            
            # Сортируем фотографии по количеству лайков (по убыванию)
            processed_photos.sort(key=lambda x: x['likes'], reverse=True)
            
            logger.info(f"Получено {len(processed_photos)} фотографий для пользователя {user_id}")
            return processed_photos
            
        except Exception as e:
            logger.error(f"Ошибка при получении фотографий пользователя {user_id}: {e}")
            return []
    
    def _get_max_size_photo_url(self, sizes: List[Dict[str, Any]]) -> Optional[str]:
        """
        Находит URL фотографии наибольшего размера.
        
        Args:
            sizes (List[Dict[str, Any]]): Список размеров фотографии
            
        Returns:
            Optional[str]: URL фотографии наибольшего размера или None
        """
        if not sizes:
            return None
        
        # Находим размер с максимальной площадью (ширина * высота)
        max_size = max(sizes, key=lambda x: x.get('width', 0) * x.get('height', 0))
        return max_size.get('url')
    
    def calculate_age_from_bdate(self, bdate: str) -> Optional[int]:
        """
        Вычисляет возраст по дате рождения.
        
        Args:
            bdate (str): Дата рождения в формате "DD.MM.YYYY" или "DD.MM"
            
        Returns:
            Optional[int]: Возраст в годах или None, если не удалось вычислить
        """
        if not bdate:
            return None
        
        try:
            # Разбиваем дату на компоненты
            date_parts = bdate.split('.')
            
            # Проверяем, что есть день, месяц и год
            if len(date_parts) < 3:
                logger.debug(f"Неполная дата рождения: {bdate}")
                return None
            
            # Извлекаем день, месяц и год
            day, month, year = map(int, date_parts[:3])
            
            # Создаем объект даты рождения
            birth_date = datetime(year, month, day)
            
            # Получаем текущую дату
            current_date = datetime.now()
            
            # Вычисляем возраст
            age = current_date.year - birth_date.year
            
            # Корректируем возраст, если день рождения еще не наступил в этом году
            if (current_date.month, current_date.day) < (birth_date.month, birth_date.day):
                age -= 1
            
            return age
            
        except (ValueError, TypeError) as e:
            logger.debug(f"Ошибка при вычислении возраста из даты {bdate}: {e}")
            return None
    
    def get_city_by_name(self, city_name: str, country_id: int = 1) -> Optional[Dict[str, Any]]:
        """
        Находит город по названию.
        
        Args:
            city_name (str): Название города
            country_id (int): ID страны (1 - Россия по умолчанию)
            
        Returns:
            Optional[Dict[str, Any]]: Информация о городе или None
        """
        try:
            # Параметры поиска города
            params = {
                'q': city_name,           # Поисковый запрос
                'country_id': country_id, # ID страны
                'count': 1                # Количество результатов
            }
            
            # Выполняем запрос к методу database.getCities
            response = self._make_request('database.getCities', params)
            
            # Извлекаем список городов
            cities = response.get('items', [])
            
            if cities:
                city = cities[0]
                logger.info(f"Найден город: {city['title']} (ID: {city['id']})")
                return city
            else:
                logger.warning(f"Город '{city_name}' не найден")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка при поиске города '{city_name}': {e}")
            return None
