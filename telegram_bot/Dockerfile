FROM python:3.11-slim

# Docker CLI o'rnatish (container boshqaruvi uchun)
RUN apt-get update && apt-get install -y \
    docker.io \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Faqat standart kutubxonalar ishlatiladi (pip kerak emas)
COPY bot.py .

CMD ["python", "-u", "bot.py"]