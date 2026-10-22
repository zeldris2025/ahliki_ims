# Ah Liki IMS — Django + gunicorn. See DOCKER.md (office) and AZURE.md (Azure).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SQLITE_PATH=/app/data/db.sqlite3 \
    MEDIA_ROOT=/app/data/media

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
# Scripts edited on Windows may carry CRLF line endings, which break the shebang.
# Static files are collected here, at build time, so the container starts faster.
RUN sed -i 's/\r$//' docker/entrypoint.sh && chmod +x docker/entrypoint.sh \
    && python manage.py collectstatic --noinput --verbosity 0 \
    && useradd --create-home --uid 1000 app && mkdir -p /app/data && chown -R app:app /app

USER app
EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
# Port, workers and logging come from gunicorn.conf.py.
CMD ["gunicorn", "ahliki_ims.wsgi:application"]
