FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p memory/daily conversations

# Default to CLI mode
CMD ["python", "main.py"]
