FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV TELEGRAM_TOKEN=your_token
ENV VK_TOKEN=your_vk_token
ENV ADMIN_IDS=123456789

CMD ["python", "main.py"]