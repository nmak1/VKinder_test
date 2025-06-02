"""
Модуль конфигурации для VKinder бота.

Этот модуль содержит все настройки и конфигурационные параметры,
необходимые для работы бота, включая токены API и настройки базы данных.
"""

import os
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
# Это позволяет безопасно хранить конфиденциальные данные
load_dotenv()

class Config:
    """
    Класс конфигурации для хранения всех настроек приложения.
    
    Attributes:
        TELEGRAM_TOKEN (str): Токен Telegram бота
        VK_TOKEN (str): Токен для доступа к API ВКонтакте
        DATABASE_URL (str): URL для подключения к базе данных
        VK_API_VERSION (str): Версия API ВКонтакте
        SEARCH_LIMIT (int): Максимальное количество результатов поиска
    """
    
    # Токен Telegram бота, получаемый от @BotFather
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    
    # Токен для доступа к API ВКонтакте
    VK_TOKEN = os.getenv('VK_TOKEN')
    
    # URL для подключения к базе данных PostgreSQL
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://user:password@localhost/vkinder')
    
    # Версия API ВКонтакте для обеспечения совместимости
    VK_API_VERSION = '5.131'
    
    # Максимальное количество результатов поиска за один запрос
    SEARCH_LIMIT = 50
    
    @classmethod
    def validate(cls):
        """
        Проверяет наличие всех необходимых переменных окружения.
        
        Raises:
            ValueError: Если отсутствуют обязательные переменные окружения
        """
        # Проверяем наличие токена Telegram
        if not cls.TELEGRAM_TOKEN:
            raise ValueError("TELEGRAM_TOKEN не найден в переменных окружения")
        
        # Проверяем наличие токена ВКонтакте
        if not cls.VK_TOKEN:
            raise ValueError("VK_TOKEN не найден в переменных окружения")
