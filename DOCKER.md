# Running Ah Liki IMS in Docker

The app runs in one container (Django + gunicorn) and is opened at **http://10.10.8.49:8080**.

## First start

1. **Stop the old server** that is using port 8080 (the `python manage.py runserver` window — press Ctrl+C).
   Do this *before* step 2 so no one adds data to the old database after it has been copied.
2. In this folder, run:

   ```
   docker compose up -d --build
   ```

3. Open **http://10.10.8.49:8080** and log in with your usual username and password.

On the first start the container copies `db.sqlite3` (and any `media/` uploads) into the `docker-data/` folder,
so everything you had carries across. From then on **`docker-data/` is the live database** —
the `db.sqlite3` in the project folder is no longer used.

## Everyday commands

| Task | Command |
|---|---|
| Start | `docker compose up -d` |
| Stop | `docker compose down` |
| See logs | `docker compose logs -f` |
| After changing code | `docker compose up -d --build` (migrations run automatically) |
| Create an admin user | `docker compose exec web python manage.py createsuperuser` |
| Django shell | `docker compose exec web python manage.py shell` |

## Live-reload mode (no rebuild after code changes)

Start the app with the dev file added:

```
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

The container then runs straight from this folder instead of the copy baked into the image:

- **Python files and templates:** gunicorn restarts its workers within about a second of a save. Refresh the browser.
- **CSS / JS in `static/`:** served as they are on disk. Refresh the browser.
- **New migrations:** run `docker compose exec web python manage.py migrate`, or restart the container.
- **`requirements.txt` or `Dockerfile` changes:** still need `--build`. Add it to the command above.

Every save goes live immediately for everyone using the app, so avoid leaving a file half-edited. To go back to
the normal baked-in mode, run `docker compose up -d --build` without the dev file.

The container restarts on its own after a reboot as long as Docker Desktop is running
(enable *Start Docker Desktop when you sign in* in Docker Desktop settings).

## Backups

Everything that matters is in **`docker-data/`**:

- `docker-data/db.sqlite3` — the database
- `docker-data/media/` — uploaded files

To back up, stop the app (`docker compose down`), copy the `docker-data` folder somewhere safe, then start it again.

## Settings — `.env`

`.env` holds the settings (it is git-ignored; `.env.example` is the template):

- `APP_PORT` — port on this machine (default `8080`).
- `DJANGO_SECRET_KEY` — already generated; keep it private.
- `DJANGO_ALLOWED_HOSTS` / `DJANGO_CSRF_TRUSTED_ORIGINS` — the addresses people type in the browser.
  **If the PC's IP or the port changes, update both**, otherwise logins fail with "CSRF verification failed".
  Then run `docker compose up -d`.

## Opening it from other computers

Other PCs on the network use **http://10.10.8.49:8080**. If they cannot connect, allow the port through
Windows Firewall (PowerShell as Administrator):

```
New-NetFirewallRule -DisplayName "Ah Liki IMS 8080" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow
```

Give this PC a fixed IP (DHCP reservation on the router) so the address does not change.

## Going back to runserver

`python manage.py runserver 0.0.0.0:8080` still works and uses the project's `db.sqlite3`
(stop Docker first: `docker compose down`). Note that it does **not** see data entered in Docker —
copy `docker-data/db.sqlite3` over `db.sqlite3` first if you need it.
