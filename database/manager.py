import logging
from contextlib import contextmanager
from typing import Optional, List, Dict, Any, Iterator

from sqlalchemy import create_engine, exc
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import SQLAlchemyError

from database.models import Base, User, Favorite, Blacklist

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, database_url: str, echo: bool = False):
        """
        Инициализация менеджера базы данных.

        :param database_url: URL для подключения к БД (например, 'sqlite:///vkinder.db')
        :param echo: Логировать SQL-запросы (для отладки)
        """
        try:
            self.engine = create_engine(
                database_url,
                echo=echo,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
                pool_recycle=3600
            )
            self.Session = scoped_session(
                sessionmaker(
                    bind=self.engine,
                    autocommit=False,
                    autoflush=False,
                    expire_on_commit=False
                )
            )
            logger.info(f"DatabaseManager initialized with URL: {database_url}")
        except Exception as e:
            logger.critical(f"Failed to initialize DatabaseManager: {e}")
            raise

    @contextmanager
    def session_scope(self) -> Iterator[scoped_session]:
        """Контекстный менеджер для сессий БД с автоматическим управлением транзакциями."""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            session.close()

    def create_tables(self) -> None:
        """Создает все таблицы в базе данных."""
        try:
            Base.metadata.create_all(self.engine)
            logger.info("Database tables created successfully")
        except SQLAlchemyError as e:
            logger.error(f"Error creating tables: {e}")
            raise

    def health_check(self) -> bool:
        """Проверяет доступность базы данных."""
        try:
            with self.engine.connect() as conn:
                conn.execute("SELECT 1")
            return True
        except exc.SQLAlchemyError as e:
            logger.error(f"Database health check failed: {e}")
            return False

    # User operations
    def get_or_create_user(self, telegram_id: int, first_name: str, last_name: Optional[str] = None) -> User:
        """Получает или создает пользователя."""
        with self.session_scope() as session:
            try:
                user = session.query(User).filter(User.telegram_id == telegram_id).first()

                if not user:
                    user = User(
                        telegram_id=telegram_id,
                        first_name=first_name,
                        last_name=last_name
                    )
                    session.add(user)
                    session.flush()
                    logger.info(f"Created new user: {telegram_id}")
                else:
                    user.first_name = first_name
                    if last_name:
                        user.last_name = last_name
                    logger.info(f"Updated existing user: {telegram_id}")

                return user
            except Exception as e:
                logger.error(f"Error in get_or_create_user: {e}")
                raise

    def update_user_vk_info(
            self,
            telegram_id: int,
            vk_id: int,
            age: Optional[int] = None,
            gender: Optional[int] = None,
            city_id: Optional[int] = None,
            city_name: Optional[str] = None
    ) -> bool:
        """Обновляет информацию о пользователе из VK."""
        with self.session_scope() as session:
            try:
                user = session.query(User).filter(User.telegram_id == telegram_id).first()
                if not user:
                    logger.warning(f"User {telegram_id} not found")
                    return False

                user.vk_id = vk_id
                if age is not None:
                    user.age = age
                if gender is not None:
                    user.gender = gender
                if city_id is not None:
                    user.city_id = city_id
                if city_name is not None:
                    user.city_name = city_name

                logger.info(f"Updated VK info for user {telegram_id}")
                return True
            except Exception as e:
                logger.error(f"Error updating VK info: {e}")
                return False

    # Favorites operations
    def add_to_favorites(
            self,
            telegram_id: int,
            target_vk_id: int,
            target_name: str,
            target_link: str
    ) -> bool:
        """Добавляет анкету в избранное."""
        with self.session_scope() as session:
            try:
                user = session.query(User).filter(User.telegram_id == telegram_id).first()
                if not user:
                    logger.warning(f"User {telegram_id} not found")
                    return False

                # Проверка на дубликат
                existing = session.query(Favorite).filter(
                    Favorite.user_id == user.id,
                    Favorite.target_vk_id == target_vk_id
                ).first()

                if existing:
                    logger.info(f"User {target_vk_id} already in favorites")
                    return False

                favorite = Favorite(
                    user_id=user.id,
                    target_vk_id=target_vk_id,
                    target_name=target_name,
                    target_link=target_link
                )
                session.add(favorite)
                logger.info(f"Added to favorites: {target_name} for user {telegram_id}")
                return True
            except Exception as e:
                logger.error(f"Error adding to favorites: {e}")
                return False

    def get_favorites(self, telegram_id: int) -> List[Dict[str, Any]]:
        """Возвращает список избранных анкет пользователя."""
        with self.session_scope() as session:
            try:
                user = session.query(User).filter(User.telegram_id == telegram_id).first()
                if not user:
                    return []

                favorites = session.query(Favorite).filter(Favorite.user_id == user.id).all()
                return [
                    {
                        'vk_id': fav.target_vk_id,
                        'name': fav.target_name,
                        'link': fav.target_link,
                        'added_at': fav.added_at
                    }
                    for fav in favorites
                ]
            except Exception as e:
                logger.error(f"Error getting favorites: {e}")
                return []

    # Blacklist operations
    def add_to_blacklist(self, telegram_id: int, blocked_vk_id: int) -> bool:
        """Добавляет пользователя в черный список."""
        with self.session_scope() as session:
            try:
                user = session.query(User).filter(User.telegram_id == telegram_id).first()
                if not user:
                    return False

                existing = session.query(Blacklist).filter(
                    Blacklist.user_id == user.id,
                    Blacklist.blocked_vk_id == blocked_vk_id
                ).first()

                if existing:
                    return False

                blacklist_entry = Blacklist(
                    user_id=user.id,
                    blocked_vk_id=blocked_vk_id
                )
                session.add(blacklist_entry)
                logger.info(f"Added to blacklist: {blocked_vk_id} for user {telegram_id}")
                return True
            except Exception as e:
                logger.error(f"Error adding to blacklist: {e}")
                return False

    def is_in_blacklist(self, telegram_id: int, vk_id: int) -> bool:
        """Проверяет, находится ли пользователь в черном списке."""
        with self.session_scope() as session:
            try:
                user = session.query(User).filter(User.telegram_id == telegram_id).first()
                if not user:
                    return False

                return session.query(Blacklist).filter(
                    Blacklist.user_id == user.id,
                    Blacklist.blocked_vk_id == vk_id
                ).first() is not None
            except Exception as e:
                logger.error(f"Error checking blacklist: {e}")
                return False

    def close(self):
        """Закрывает соединения с БД."""
        self.Session.remove()
        self.engine.dispose()
        logger.info("Database connections closed")