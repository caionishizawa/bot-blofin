# Bot de Trading — Telegram + Scanner
FROM python:3.11-slim

WORKDIR /app

# System deps for matplotlib
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

WORKDIR /app/src

CMD ["python", "bot.py"]
