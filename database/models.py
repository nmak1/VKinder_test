from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, validates
from datetime import datetime

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    vk_id = Column(Integer, nullable=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(Integer, nullable=True)
    city_id = Column(Integer, nullable=True)
    city_name = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    favorites = relationship("Favorite", back_populates="user", cascade="all, delete-orphan")
    blacklist = relationship("Blacklist", back_populates="user", cascade="all, delete-orphan")

    @validates('age')
    def validate_age(self, key, age):
        if age is not None and (age < 14 or age > 100):
            raise ValueError("Age must be between 14 and 100")
        return age


class Favorite(Base):
    __tablename__ = 'favorites'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    target_vk_id = Column(Integer, nullable=False)
    target_name = Column(String(200), nullable=False)
    target_link = Column(String(200), nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="favorites")


class Blacklist(Base):
    __tablename__ = 'blacklist'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    blocked_vk_id = Column(Integer, nullable=False)
    blocked_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="blacklist")