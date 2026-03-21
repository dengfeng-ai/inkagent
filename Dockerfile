FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p memory/daily conversations

# Default to Telegram bot; override with: docker run ... inkagent python main.py
CMD ["python", "bot.py"]
