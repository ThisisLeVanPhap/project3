FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DEFAULT_TIMEOUT=600

WORKDIR /app

COPY chatbot/requirements-docker.txt /app/requirements-docker.txt
RUN pip install --no-cache-dir --retries 10 -r /app/requirements-docker.txt

COPY chatbot /app

EXPOSE 8000

CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000"]
