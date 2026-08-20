FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
# Required at startup: the schema is created by `alembic upgrade head`.
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

# Runs as an unprivileged user: a bug in the upload or storage handling then
# stays a bug in that user's own files, not root inside the container.
# Created before the volume mount point exists so `docker compose up` gives
# the named `uploads_data` volume the same ownership on first use.
RUN useradd --system --create-home --uid 10001 app \
    && mkdir -p /app/uploads \
    && chown -R app:app /app
USER app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
