
# VKinder Bot 🤖❤️

Telegram-бот для поиска интересных людей в VK на основе ваших предпочтений.

![VKinder Bot Demo](demo.gif) *(Пример работы бота)*

## 🔥 Возможности

- 🔍 Поиск людей в VK по заданным параметрам (возраст, город)
- ❤️ Сохранение понравившихся анкет в избранное
- 🚫 Добавление в черный список
- 📸 Просмотр фотографий из профиля
- 📊 Умный алгоритм подбора (топ-3 фото по лайкам)

## ⚙️ Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/maksimdemin18/VKinder_test
cd vkinder-bot
Установите зависимости:

bash
pip install -r requirements.txt
Создайте файл .env и заполните его:

ini
TELEGRAM_TOKEN=ваш_токен_бота
VK_TOKEN=ваш_vk_api_токен
ADMIN_IDS=123456789 # ID админов через запятую
DATABASE_URL=sqlite:///vkinder.db
🚀 Запуск
bash
python main.py
Или через Docker:

bash
docker build -t vkinder-bot .
docker run -d --name vkinder-bot vkinder-bot
🛠 Технологии
Python 3.9+

pyTelegramBotAPI

SQLAlchemy (SQLite/PostgreSQL)

VK API

Docker (опционально)

📚 Команды бота
Команда	Описание
/start	Начать работу с ботом
/help	Получить справку
/search	Начать поиск анкет
/favorites	Показать избранные анкеты
🌟 Особенности архитектуры
text
├── config/           # Конфигурация
├── database/         # Модели и работа с БД
├── services/         # Бизнес-логика
├── bot/              # Telegram-бот
├── tests/            # Тесты
└── main.py           # Точка входа
📈 Статистика
Бот собирает базовую статистику:

Количество пользователей

Выполненных поисков

Добавлений в избранное

🤝 Разработка
Создайте виртуальное окружение:

bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
Установите dev-зависимости:

bash
pip install -r requirements-dev.txt
Запустите тесты:

bash
pytest tests/
📜 Лицензия
MIT License. Подробнее в файле LICENSE.

Note: Для работы бота необходим токен VK API с правами: friends, photos, groups.
Бот не хранит персональные данные пользователей VK.