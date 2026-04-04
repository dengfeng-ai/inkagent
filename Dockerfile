FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY inkagent/ inkagent/
RUN pip install --no-cache-dir .

COPY skills/ skills/

RUN mkdir -p memory/daily conversations

# Default to CLI mode
CMD ["python", "-m", "inkagent"]
