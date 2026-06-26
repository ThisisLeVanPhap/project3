FROM python:3.11-slim

ARG INSTALL_LOCAL_AI=false

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DEFAULT_TIMEOUT=600

WORKDIR /app

COPY chatbot/requirements-docker-base.txt /app/requirements-docker-base.txt
RUN pip install --no-cache-dir --retries 10 -r /app/requirements-docker-base.txt

COPY chatbot/requirements-docker.txt /app/requirements-docker.txt
RUN if [ "$INSTALL_LOCAL_AI" = "true" ]; then \
        pip install --no-cache-dir --retries 10 -r /app/requirements-docker.txt; \
    fi

COPY chatbot /app
COPY data_pipeline /app/data_pipeline

EXPOSE 8000

CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000"]
