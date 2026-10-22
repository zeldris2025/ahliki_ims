# Putting Ah Liki IMS on Azure

The app goes on **Azure App Service** (Linux web app, not a VM). The steps use the container option, which runs
the same Docker image as the office install. Publishing as **Code** also works; see
[Option: Publish as "Code"](#option-publish-as-code-instead-of-a-container).
The database moves to **Azure Database for PostgreSQL**. Azure gives the site an address like
`https://<app-name>.azurewebsites.net`, and the app trusts that address on its own, so no domain is
written anywhere. A custom domain can be added later (see the end of this guide).

## What is already set up in the code

| | |
|---|---|
| Address | Picks up the Azure address on its own (`WEBSITE_HOSTNAME`), for both host checks and logins (CSRF). |
| HTTPS | On automatically on Azure: redirects to https and uses secure cookies. The office Docker install stays on http. |
| Safe defaults | On Azure, `DEBUG` is off unless set, and the app refuses to start without `DJANGO_SECRET_KEY`. |
| Database | Uses PostgreSQL when `DATABASE_URL` is set, otherwise the SQLite file as before. |
| Port | gunicorn listens on `PORT` / `WEBSITES_PORT` (8000 by default). See `gunicorn.conf.py`. |
| Health check | `/healthz` returns `ok` for Azure's health probe. |
| Uploaded invoices | `/media/` now needs a login, because the site can be reached from the internet. |
| Logs | Go to the console, which shows in Azure's **Log stream**. |
| Start-up | Migrations run on every start. Static files are built into the image. |

## What you need

- An Azure subscription, plus the **Azure CLI** (`winget install Microsoft.AzureCLI`). Sign in with `az login`.
- Docker is **not** needed for this: the image is built in Azure (`az acr build`).

Run the commands below in **PowerShell**, from this project folder. First pick your names. Each name must
be unique across Azure, and the app name becomes the web address:

```powershell
$RG       = "ahliki-ims-rg"
$LOCATION = "australiaeast"          # nearest region to Samoa
$ACR      = "ahlikiimsacr"           # letters and numbers only
$APP      = "ahliki-ims"             # -> https://ahliki-ims.azurewebsites.net (or similar)
$PLAN     = "ahliki-ims-plan"
$PG       = "ahliki-ims-db"
$PGUSER   = "ahlikiadmin"
$PGPASS   = "<choose a strong password>"
```

## 1. Resource group and image

```powershell
az group create -n $RG -l $LOCATION
az acr create -g $RG -n $ACR --sku Basic
az acr build -r $ACR -t ahliki-ims:latest .
```

`az acr build` uploads the project, but not the files listed in `.dockerignore` (`.env`, `venv`, `docker-data`),
and builds the image in Azure.

## 2. Database

```powershell
az postgres flexible-server create -g $RG -n $PG -l $LOCATION `
  --tier Burstable --sku-name Standard_B1ms --storage-size 32 --version 16 `
  --admin-user $PGUSER --admin-password $PGPASS --public-access 0.0.0.0
az postgres flexible-server db create -g $RG -s $PG -d ahliki_ims
```

`--public-access 0.0.0.0` lets other Azure services, such as the web app, connect. Nobody else can.

## 3. Web app

```powershell
az appservice plan create -g $RG -n $PLAN --is-linux --sku B1
$ACR_ID = az acr show -n $ACR --query id -o tsv
az webapp create -g $RG -p $PLAN -n $APP `
  --container-image-name "$ACR.azurecr.io/ahliki-ims:latest" `
  --assign-identity "[system]" --role AcrPull --scope $ACR_ID --acr-use-identity
```

App settings. Generate the secret key with
`python -c "import secrets; print(secrets.token_urlsafe(50))"`:

```powershell
az webapp config appsettings set -g $RG -n $APP --settings `
  WEBSITES_PORT=8000 `
  DJANGO_SECRET_KEY="<paste the generated key>" `
  DATABASE_URL="postgres://${PGUSER}:${PGPASS}@${PG}.postgres.database.azure.com:5432/ahliki_ims?sslmode=require" `
  WEBSITES_ENABLE_APP_SERVICE_STORAGE=true `
  MEDIA_ROOT=/home/data/media `
  TRACKING_AUTO_REFRESH_HOURS=0
```

If the password contains `@ : / ? #` or `%`, URL-encode it in `DATABASE_URL` (for example, `@` becomes `%40`).

Health check, HTTPS only, and container logs:

```powershell
az webapp config set -g $RG -n $APP --generic-configurations '{\"healthCheckPath\": \"/healthz\"}'
az webapp update -g $RG -n $APP --https-only true
az webapp log config -g $RG -n $APP --docker-container-logging filesystem
```

The new database is empty for now. Step 4 copies your data into it.

## 4. Move the existing data across

Your live data is in **`docker-data/db.sqlite3`**, from the office Docker install. Copy it into PostgreSQL
from this PC:

```powershell
# a) Let this PC reach the database for a moment
$MYIP = (Invoke-RestMethod https://api.ipify.org)
az postgres flexible-server firewall-rule create -g $RG -n $PG --rule-name setup-pc --start-ip-address $MYIP --end-ip-address $MYIP

# b) Stop the office app so nothing changes during the copy, then export
docker compose down
pip install -r requirements.txt
$env:SQLITE_PATH = "docker-data\db.sqlite3"
python -X utf8 manage.py dumpdata --natural-foreign --natural-primary `
  -e contenttypes -e auth.permission -e admin.logentry -e sessions --indent 2 -o azure-data.json

# c) Create the tables in Azure and load the data
Remove-Item Env:SQLITE_PATH
$env:DATABASE_URL = "postgres://${PGUSER}:${PGPASS}@${PG}.postgres.database.azure.com:5432/ahliki_ims?sslmode=require"
python manage.py migrate
python -X utf8 manage.py loaddata azure-data.json
Remove-Item Env:DATABASE_URL

# d) Close the database to this PC again, and delete the export (it holds every record)
az postgres flexible-server firewall-rule delete -g $RG -n $PG --rule-name setup-pc --yes
Remove-Item azure-data.json
```

Every user keeps their username and password.

If there are uploaded invoices in `docker-data/media`, upload them to `/home/data/media` on the web app
(Portal → the web app → **Advanced Tools (Kudu)** → **Files**).

## 5. Open it

```powershell
az webapp restart -g $RG -n $APP
az webapp show -g $RG -n $APP --query defaultHostName -o tsv
```

Open `https://<that address>` and log in. If the page doesn't load, check
Portal → the web app → **Log stream**.

## Option: Publish as "Code" instead of a container

When you create the web app in the portal, App Service asks **Publish: Code or Container**. Steps 1 and 3
above are for **Container**. To use **Code**, skip `az acr ...` in step 1 and replace step 3 with the
commands below. Steps 2, 4 and 5 stay the same.

```powershell
az appservice plan create -g $RG -n $PLAN --is-linux --sku B1
az webapp create -g $RG -p $PLAN -n $APP --runtime "PYTHON:3.13"
az webapp config set -g $RG -n $APP `
  --startup-file "python manage.py migrate --noinput && gunicorn ahliki_ims.wsgi:application"
az webapp config appsettings set -g $RG -n $APP --settings `
  SCM_DO_BUILD_DURING_DEPLOYMENT=true `
  DJANGO_SECRET_KEY="<paste the generated key>" `
  DATABASE_URL="postgres://${PGUSER}:${PGPASS}@${PG}.postgres.database.azure.com:5432/ahliki_ims?sslmode=require" `
  MEDIA_ROOT=/home/data/media `
  TRACKING_AUTO_REFRESH_HOURS=0
```

The health check and HTTPS only commands from step 3 apply here too. Leave out the `--docker-container-logging` line.

Deploy the code. This uploads only committed files, so `.env` and `venv` are never sent. Commit your
changes first:

```powershell
git archive -o deploy.zip HEAD
az webapp deploy -g $RG -n $APP --src-path deploy.zip --type zip
Remove-Item deploy.zip
```

Azure installs `requirements.txt` and runs `collectstatic` itself. Run the same three lines for every update.

## Updating after code changes (container)

```powershell
az acr build -r $ACR -t ahliki-ims:latest .
az webapp restart -g $RG -n $APP
```

Migrations run on their own when the app starts.

## Adding your own domain later

1. Portal → the web app → **Custom domains** → **Add custom domain**. Add the DNS records it asks for.
2. Choose **App Service Managed Certificate** (free) to get HTTPS for that domain.
3. Tell the app about the domain. Comma separated; the `azurewebsites.net` address keeps working:

   ```powershell
   az webapp config appsettings set -g $RG -n $APP --settings `
     DJANGO_ALLOWED_HOSTS="ims.example.com" `
     DJANGO_CSRF_TRUSTED_ORIGINS="https://ims.example.com"
   ```

## App settings reference

| Setting | Needed | What it does |
|---|---|---|
| `DJANGO_SECRET_KEY` | **yes** | Signs logins. Keep it private. If it changes, everyone is logged out. |
| `DATABASE_URL` | yes, for PostgreSQL | `postgres://user:pass@host:5432/db?sslmode=require` |
| `WEBSITES_PORT` | yes | `8000`, the port the container listens on. |
| `WEBSITES_ENABLE_APP_SERVICE_STORAGE` | yes | `true` keeps `/home` (uploads) across restarts. |
| `MEDIA_ROOT` | yes | `/home/data/media`, where uploaded invoices are stored. |
| `DJANGO_ALLOWED_HOSTS` | later | Custom domain(s). The Azure address is added on its own. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | later | `https://` + the custom domain(s). |
| `TRACKING_AUTO_REFRESH_HOURS` | no | `0` turns off the old Terminal49 refresher. |
| `WEB_CONCURRENCY` | no | gunicorn workers (default 3). |
| `DJANGO_DEBUG` | no | Leave unset (off). Never turn it on in production. |
| `DJANGO_HSTS_SECONDS` | no | HSTS length (default 3600). Raise it once the final domain is settled. |

## Without PostgreSQL (smaller and cheaper, but less safe)

Skip step 2 and leave out `DATABASE_URL`. Set `SQLITE_PATH=/home/data/db.sqlite3` and `WEB_CONCURRENCY=1`.
Keep the plan at **one instance**. Before `az acr build`, copy `docker-data\db.sqlite3` over the project's
`db.sqlite3`; the first start copies it to `/home/data`. Azure keeps `/home` on network storage, where SQLite
can hit "database is locked" errors and is at more risk of corruption. Use PostgreSQL for anything people
rely on every day.

## Before going live

- **Passwords:** the site will be on the internet, and the app does not enforce password strength
  (`AUTH_PASSWORD_VALIDATORS` is empty). Make sure every account has a strong password, especially admins.
- **Backups:** Azure PostgreSQL backs itself up every day (7 days by default). Uploads in `/home` are covered
  by App Service backups (Portal → the web app → **Backups**).
- **Office install:** after the move, stop using the office Docker copy (`docker compose down`), so people
  don't keep entering data into two systems.
