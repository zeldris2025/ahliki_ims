#!/bin/sh
# Prepares the container on every start, then runs gunicorn (or whatever command was given).
set -e

for dir in "$MEDIA_ROOT" "$([ -z "$DATABASE_URL" ] && dirname "$SQLITE_PATH")"; do
    [ -n "$dir" ] || continue
    mkdir -p "$dir"
    if ! touch "$dir/.write-test" 2>/dev/null; then
        echo "ERROR: $dir is not writable by the app user — check the storage mount." >&2
        exit 1
    fi
    rm -f "$dir/.write-test"
done

# SQLite only — first run: start from the database that ships with the project, so existing data comes across.
if [ -z "$DATABASE_URL" ] && [ ! -f "$SQLITE_PATH" ] && [ -f /app/db.sqlite3 ]; then
    echo "No database at $SQLITE_PATH yet — copying the project's db.sqlite3."
    cp /app/db.sqlite3 "$SQLITE_PATH"
fi
# Same for uploaded files.
if [ -d /app/media ] && [ -z "$(ls -A "$MEDIA_ROOT" 2>/dev/null)" ]; then
    cp -r /app/media/. "$MEDIA_ROOT"/ 2>/dev/null || true
fi

python manage.py migrate --noinput

exec "$@"
