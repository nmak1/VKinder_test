"""
Модуль для работы с базой данных.

Этот модуль содержит все классы и функции для работы с базой данных,
включая модели данных и операции CRUD (Create, Read, Update, Delete).
"""

from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, scoped_session
from datetime import datetime
from typing import List, Optional, Dict, Any
import logging

# Создаем базовый класс для всех моделей
Base = declarative_base()

# Настраиваем логирование для отслеживания операций с БД
logger = logging.getLogger(__name__)

class User(Base):
    """
    Модель пользователя Telegram бота.
    
    Хранит информацию о пользователях, которые взаимодействуют с ботом,
    включая их данные из ВКонтакте и настройки поиска.
    
    Attributes:
        id (int): Уникальный идентификатор пользователя в БД
        telegram_id (int): ID пользователя в Telegram
        vk_id (int): ID пользователя в ВКонтакте
        first_name (str): Имя пользователя
        last_name (str): Фамилия пользователя
        age (int): Возраст пользователя
        gender (int): Пол пользователя (1 - женский, 2 - мужской)
        city_id (int): ID города пользователя в ВКонтакте
        city_name (str): Название города пользователя
        created_at (datetime): Дата создания записи
        is_active (bool): Активен ли пользователь
    """
    
    # Название таблицы в базе данных
    __tablename__ = 'users'
    
    # Уникальный идентификатор пользователя (первичный ключ)
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # ID пользователя в Telegram (уникальный)
    telegram_id = Column(Integer, unique=True, nullable=False)
    
    # ID пользователя в ВКонтакте (может быть пустым)
    vk_id = Column(Integer, nullable=True)
    
    # Имя пользователя (максимум 100 символов)
    first_name = Column(String(100), nullable=False)
    
    # Фамилия пользователя (максимум 100 символов)
    last_name = Column(String(100), nullable=True)
    
    # Возраст пользователя
    age = Column(Integer, nullable=True)
    
    # Пол пользователя (1 - женский, 2 - мужской)
    gender = Column(Integer, nullable=True)
    
    # ID города в ВКонтакте
    city_id = Column(Integer, nullable=True)
    
    # Название города
    city_name = Column(String(100), nullable=True)
    
    # Дата создания записи
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Флаг активности пользователя
    is_active = Column(Boolean, default=True)
    
    # Связь с избранными анкетами (один ко многим)
    favorites = relationship("Favorite", back_populates="user", cascade="all, delete-orphan")
    
    # Связь с черным списком (один ко многим)
    blacklist = relationship("Blacklist", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        """
        Строковое представление объекта пользователя.
        
        Returns:
            str: Строковое представление пользователя
        """
        return f"<User(telegram_id={self.telegram_id}, name='{self.first_name} {self.last_name}')>"


class Favorite(Base):
    """
    Модель избранных анкет пользователя.
    
    Хранит информацию об анкетах, которые пользователь добавил в избранное.
    
    Attributes:
        id (int): Уникальный идентификатор записи
        user_id (int): ID пользователя (внешний ключ)
        target_vk_id (int): ID пользователя ВКонтакте, добавленного в избранное
        target_name (str): Имя пользователя из избранного
        target_link (str): Ссылка на профиль в ВКонтакте
        added_at (datetime): Дата добавления в избранное
    """
    
    # Название таблицы в базе данных
    __tablename__ = 'favorites'
    
    # Уникальный идентификатор записи
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Внешний ключ на таблицу пользователей
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # ID пользователя ВКонтакте, добавленного в избранное
    target_vk_id = Column(Integer, nullable=False)
    
    # Имя пользователя из избранного
    target_name = Column(String(200), nullable=False)
    
    # Ссылка на профиль в ВКонтакте
    target_link = Column(String(200), nullable=False)
    
    # Дата добавления в избранное
    added_at = Column(DateTime, default=datetime.utcnow)
    
    # Обратная связь с пользователем
    user = relationship("User", back_populates="favorites")
    
    def __repr__(self) -> str:
        """
        Строковое представление избранной анкеты.
        
        Returns:
            str: Строковое представление избранной анкеты
        """
        return f"<Favorite(user_id={self.user_id}, target_name='{self.target_name}')>"


class Blacklist(Base):
    """
    Модель черного списка пользователя.
    
    Хранит информацию об анкетах, которые пользователь добавил в черный список
    и которые не должны показываться в результатах поиска.
    
    Attributes:
        id (int): Уникальный идентификатор записи
        user_id (int): ID пользователя (внешний ключ)
        blocked_vk_id (int): ID заблокированного пользователя ВКонтакте
        blocked_at (datetime): Дата добавления в черный список
    """
    
    # Название таблицы в базе данных
    __tablename__ = 'blacklist'
    
    # Уникальный идентификатор записи
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Внешний ключ на таблицу пользователей
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # ID заблокированного пользователя ВКонтакте
    blocked_vk_id = Column(Integer, nullable=False)
    
    # Дата добавления в черный список
    blocked_at = Column(DateTime, default=datetime.utcnow)
    
    # Обратная связь с пользователем
    user = relationship("User", back_populates="blacklist")
    
    def __repr__(self) -> str:
        """
        Строковое представление записи черного списка.
        
        Returns:
            str: Строковое представление записи черного списка
        """
        return f"<Blacklist(user_id={self.user_id}, blocked_vk_id={self.blocked_vk_id})>"


class DatabaseManager:
    """
    Менеджер для работы с базой данных.
    
    Предоставляет методы для выполнения операций CRUD с базой данных,
    включая создание, чтение, обновление и удаление записей.
    
    Attributes:
        engine: Движок SQLAlchemy для подключения к БД
        Session: Фабрика сессий для работы с БД
    """
    
    def __init__(self, database_url: str):
        """
        Инициализация менеджера базы данных.
        
        Args:
            database_url (str): URL для подключения к базе данных
        """
        # Создаем движок для подключения к базе данных
        self.engine = create_engine(database_url, echo=False)
        
        # Создаем фабрику сессий с автоматическим управлением потоками
        self.Session = scoped_session(sessionmaker(bind=self.engine))
        
        # Логируем успешную инициализацию
        logger.info("DatabaseManager инициализирован")
    
    def create_tables(self) -> None:
        """
        Создает все таблицы в базе данных.
        
        Использует метаданные моделей для создания соответствующих таблиц.
        """
        try:
            # Создаем все таблицы на основе определенных моделей
            Base.metadata.create_all(self.engine)
            logger.info("Таблицы базы данных созданы успешно")
        except Exception as e:
            # Логируем ошибку при создании таблиц
            logger.error(f"Ошибка при создании таблиц: {e}")
            raise
    
    def get_or_create_user(self, telegram_id: int, first_name: str, 
                          last_name: Optional[str] = None) -> User:
        """
        Получает существующего пользователя или создает нового.
        
        Args:
            telegram_id (int): ID пользователя в Telegram
            first_name (str): Имя пользователя
            last_name (Optional[str]): Фамилия пользователя
            
        Returns:
            User: Объект пользователя
        """
        # Создаем новую сессию для работы с БД
        session = self.Session()
        
        try:
            # Ищем существующего пользователя по Telegram ID
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            
            if user:
                # Если пользователь найден, обновляем его данные
                user.first_name = first_name
                if last_name:
                    user.last_name = last_name
                logger.info(f"Обновлен пользователь: {telegram_id}")
            else:
                # Если пользователь не найден, создаем нового
                user = User(
                    telegram_id=telegram_id,
                    first_name=first_name,
                    last_name=last_name
                )
                session.add(user)
                logger.info(f"Создан новый пользователь: {telegram_id}")
            
            # Сохраняем изменения в базе данных
            session.commit()
            return user
            
        except Exception as e:
            # В случае ошибки откатываем транзакцию
            session.rollback()
            logger.error(f"Ошибка при работе с пользователем {telegram_id}: {e}")
            raise
        finally:
            # Закрываем сессию в любом случае
            session.close()
    
    def update_user_vk_info(self, telegram_id: int, vk_id: int, 
                           age: Optional[int] = None, gender: Optional[int] = None,
                           city_id: Optional[int] = None, city_name: Optional[str] = None) -> bool:
        """
        Обновляет информацию пользователя из ВКонтакте.
        
        Args:
            telegram_id (int): ID пользователя в Telegram
            vk_id (int): ID пользователя в ВКонтакте
            age (Optional[int]): Возраст пользователя
            gender (Optional[int]): Пол пользователя
            city_id (Optional[int]): ID города
            city_name (Optional[str]): Название города
            
        Returns:
            bool: True если обновление прошло успешно, False иначе
        """
        session = self.Session()
        
        try:
            # Находим пользователя по Telegram ID
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            
            if not user:
                logger.warning(f"Пользователь с telegram_id {telegram_id} не найден")
                return False
            
            # Обновляем информацию из ВКонтакте
            user.vk_id = vk_id
            if age is not None:
                user.age = age
            if gender is not None:
                user.gender = gender
            if city_id is not None:
                user.city_id = city_id
            if city_name is not None:
                user.city_name = city_name
            
            # Сохраняем изменения
            session.commit()
            logger.info(f"Обновлена VK информация для пользователя {telegram_id}")
            return True
            
        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка при обновлении VK информации: {e}")
            return False
        finally:
            session.close()
    
    def add_to_favorites(self, telegram_id: int, target_vk_id: int, 
                        target_name: str, target_link: str) -> bool:
        """
        Добавляет анкету в избранное пользователя.
        
        Args:
            telegram_id (int): ID пользователя в Telegram
            target_vk_id (int): ID пользователя ВК для добавления в избранное
            target_name (str): Имя пользователя для добавления
            target_link (str): Ссылка на профиль
            
        Returns:
            bool: True если добавление прошло успешно, False иначе
        """
        session = self.Session()
        
        try:
            # Находим пользователя
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                logger.warning(f"Пользователь {telegram_id} не найден")
                return False
            
            # Проверяем, нет ли уже такой записи в избранном
            existing = session.query(Favorite).filter(
                Favorite.user_id == user.id,
                Favorite.target_vk_id == target_vk_id
            ).first()
            
            if existing:
                logger.info(f"Пользователь {target_vk_id} уже в избранном у {telegram_id}")
                return False
            
            # Создаем новую запись в избранном
            favorite = Favorite(
                user_id=user.id,
                target_vk_id=target_vk_id,
                target_name=target_name,
                target_link=target_link
            )
            
            session.add(favorite)
            session.commit()
            logger.info(f"Добавлен в избранное: {target_name} для пользователя {telegram_id}")
            return True
            
        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка при добавлении в избранное: {e}")
            return False
        finally:
            session.close()
    
    def get_favorites(self, telegram_id: int) -> List[Dict[str, Any]]:
        """
        Получает список избранных анкет пользователя.
        
        Args:
            telegram_id (int): ID пользователя в Telegram
            
        Returns:
            List[Dict[str, Any]]: Список избранных анкет
        """
        session = self.Session()
        
        try:
            # Находим пользователя
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                return []
            
            # Получаем все избранные анкеты пользователя
            favorites = session.query(Favorite).filter(Favorite.user_id == user.id).all()
            
            # Преобразуем в список словарей
            result = []
            for fav in favorites:
                result.append({
                    'vk_id': fav.target_vk_id,
                    'name': fav.target_name,
                    'link': fav.target_link,
                    'added_at': fav.added_at
                })
            
            logger.info(f"Получено {len(result)} избранных для пользователя {telegram_id}")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при получении избранного: {e}")
            return []
        finally:
            session.close()
    
    def add_to_blacklist(self, telegram_id: int, blocked_vk_id: int) -> bool:
        """
        Добавляет пользователя в черный список.
        
        Args:
            telegram_id (int): ID пользователя в Telegram
            blocked_vk_id (int): ID пользователя ВК для блокировки
            
        Returns:
            bool: True если добавление прошло успешно, False иначе
        """
        session = self.Session()
        
        try:
            # Находим пользователя
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                return False
            
            # Проверяем, нет ли уже такой записи в черном списке
            existing = session.query(Blacklist).filter(
                Blacklist.user_id == user.id,
                Blacklist.blocked_vk_id == blocked_vk_id
            ).first()
            
            if existing:
                return False
            
            # Создаем новую запись в черном списке
            blacklist_entry = Blacklist(
                user_id=user.id,
                blocked_vk_id=blocked_vk_id
            )
            
            session.add(blacklist_entry)
            session.commit()
            logger.info(f"Добавлен в черный список: {blocked_vk_id} для пользователя {telegram_id}")
            return True
            
        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка при добавлении в черный список: {e}")
            return False
        finally:
            session.close()
    
    def is_in_blacklist(self, telegram_id: int, vk_id: int) -> bool:
        """
        Проверяет, находится ли пользователь в черном списке.
        
        Args:
            telegram_id (int): ID пользователя в Telegram
            vk_id (int): ID пользователя ВК для проверки
            
        Returns:
            bool: True если пользователь в черном списке, False иначе
        """
        session = self.Session()
        
        try:
            # Находим пользователя
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                return False
            
            # Проверяем наличие в черном списке
            blacklist_entry = session.query(Blacklist).filter(
                Blacklist.user_id == user.id,
                Blacklist.blocked_vk_id == vk_id
            ).first()
            
            return blacklist_entry is not None
            
        except Exception as e:
            logger.error(f"Ошибка при проверке черного списка: {e}")
            return False
        finally:
            session.close()
    
    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """
        Получает пользователя по Telegram ID.
        
        Args:
            telegram_id (int): ID пользователя в Telegram
            
        Returns:
            Optional[User]: Объект пользователя или None
        """
        session = self.Session()
        
        try:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            return user
        except Exception as e:
            logger.error(f"Ошибка при получении пользователя: {e}")
            return None
        finally:
            session.close()
