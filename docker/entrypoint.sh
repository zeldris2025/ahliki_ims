#!/bin/sh
# Prepares the container on every start, then runs gunicorn (or whatever command was given).
set -e

mkdir -p "$(dirname "$SQLITE_PATH")" "$MEDIA_ROOT"

# First run: start from the database that ships with the project, so existing data comes across.
if [ ! -f "$SQLITE_PATH" ] && [ -f /app/db.sqlite3 ]; then
    echo "No database at $SQLITE_PATH yet — copying the project's db.sqlite3."
    cp /app/db.sqlite3 "$SQLITE_PATH"
fi
# Same for uploaded files.
if [ -d /app/media ] && [ -z "$(ls -A "$MEDIA_ROOT" 2>/dev/null)" ]; then
    cp -r /app/media/. "$MEDIA_ROOT"/ 2>/dev/null || true
fi

python manage.py migrate --noinput
python manage.py collectstatic --noinput --verbosity 0

exec "$@"
