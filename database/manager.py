from sqlalchemy import create_engine, exc
from sqlalchemy.orm import sessionmaker, scoped_session
from .models import Base
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, database_url: str):
        self.engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20
        )
        self.Session = scoped_session(
            sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False
            )
        )

    def create_tables(self):
        try:
            Base.metadata.create_all(self.engine)
            logger.info("Tables created successfully")
        except exc.SQLAlchemyError as e:
            logger.error(f"Error creating tables: {e}")
            raise

    def health_check(self):
        try:
            with self.engine.connect() as conn:
                conn.execute("SELECT 1")
            return True
        except exc.SQLAlchemyError as e:
            logger.error(f"Database health check failed: {e}")
            return False

    def get_user(self, telegram_id: int):
        session = self.Session()
        try:
            return session.query(User).filter(User.telegram_id == telegram_id).first()
        finally:
            session.close()

    # ... другие методы CRUD ...