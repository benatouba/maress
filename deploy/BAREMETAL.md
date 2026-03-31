# Bare-Metal Deployment (Ubuntu/Debian)

This guide deploys MaRESS directly on a Linux server without Docker, using:

- Caddy for HTTPS + reverse proxy
- FastAPI (uvicorn) backend
- Celery worker
- PostgreSQL + Redis as system services
- Built static Vue frontend served by Caddy

## 1) Server prerequisites

- Public DNS record pointing your domain to the server IP
- Open firewall ports `80` and `443`
- A non-root deploy user (examples below use `ben` and `/home/ben/projects/maress`)

## 2) Install system packages

```bash
sudo apt update
sudo apt install -y git curl ca-certificates gnupg lsb-release redis-server postgresql postgresql-contrib
```

## 3) Install Node.js + pnpm

Use Node 24.x (recommended by this repo frontend docs):

```bash
curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
sudo apt install -y nodejs
sudo corepack enable
```

## 4) Install Python 3.12 + uv

```bash
sudo apt install -y python3.12 python3.12-venv
curl -LsSf https://astral.sh/uv/install.sh | sh
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

## 5) Install Caddy

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install -y caddy
```

## 6) Clone repository

```bash
git clone <repo-url> /home/ben/projects/maress
cd /home/ben/projects/maress
```

## 7) Configure PostgreSQL

Create DB + user (replace placeholders):

```bash
sudo -u postgres psql
```

Run in psql:

```sql
CREATE USER maress WITH PASSWORD 'CHANGE_ME_STRONG_PASSWORD';
CREATE DATABASE maress OWNER maress;
\q
```

## 8) Configure environment variables

Backend settings load from `/home/ben/projects/maress/.env.local` by default.

Create and edit it:

```bash
cp /home/ben/projects/maress/.env.local /home/ben/projects/maress/.env.local.bak.$(date +%F-%H%M%S)
nano /home/ben/projects/maress/.env.local
```

Set at least these keys correctly for production:

- `ENVIRONMENT=production`
- `POSTGRES_SERVER=localhost`
- `POSTGRES_PORT=5432`
- `POSTGRES_DB=maress`
- `POSTGRES_USER=maress`
- `POSTGRES_PASSWORD=<strong password>`
- `CELERY_BROKER_URL=redis://localhost:6379/0`
- `CELERY_RESULT_BACKEND=redis://localhost:6379/1`
- `FRONTEND_HOST=https://your-domain.example`
- `BACKEND_CORS_ORIGINS=["https://your-domain.example"]` or comma-separated equivalent
- `SECRET_KEY=<strong random value>`
- `ENCRYPTION_KEY=<fernet key>`
- `FIRST_SUPERUSER=<admin email>`
- `FIRST_SUPERUSER_PASSWORD=<strong password>`
- Zotero credentials (`ZOTERO_API_KEY`, `ZOTERO_USER_ID`, `ZOTERO_LIBRARY_TYPE`)

Generate secrets quickly:

```bash
openssl rand -hex 32
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## 9) Backend install + DB init

```bash
cd /home/ben/projects/maress/backend
uv sync
bash scripts/prestart.sh
```

## 10) Frontend build

Use same-origin API path at build time:

```bash
cd /home/ben/projects/maress/frontend
pnpm install --frozen-lockfile
VITE_API_V1_URL=/api/v1 pnpm run build
```

## 11) Configure Caddy

Copy the provided bare-metal template:

```bash
sudo cp /home/ben/projects/maress/caddy/Caddyfile.baremetal /etc/caddy/Caddyfile
```

Edit `/etc/caddy/Caddyfile` and set your site address/domain and frontend path.

Example:

```caddyfile
your-domain.example {
  encode zstd gzip

  @api path /api/*
  reverse_proxy @api 127.0.0.1:8000

  root * /home/ben/projects/maress/frontend/dist
  try_files {path} /index.html
  file_server
}
```

Validate and reload:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

## 12) Install and start systemd units

Copy included service files:

```bash
sudo cp /home/ben/projects/maress/deploy/systemd/maress-backend.service /etc/systemd/system/
sudo cp /home/ben/projects/maress/deploy/systemd/maress-worker.service /etc/systemd/system/
sudo cp /home/ben/projects/maress/deploy/systemd/maress-frontend-build.service /etc/systemd/system/
```

If your username/path differs from `ben` and `/home/ben/projects/maress`, edit those unit files in `/etc/systemd/system/`.

Start services:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now redis-server
sudo systemctl enable --now postgresql
sudo systemctl start maress-frontend-build.service
sudo systemctl enable --now maress-backend.service
sudo systemctl enable --now maress-worker.service
sudo systemctl enable --now caddy
```

## 13) Verify deployment

```bash
systemctl status maress-backend maress-worker caddy --no-pager
curl -I https://your-domain.example
curl https://your-domain.example/api/v1/utils/health-check
```

Logs:

```bash
journalctl -u maress-backend -f
journalctl -u maress-worker -f
journalctl -u caddy -f
```

## 14) Updating deployment

```bash
cd /home/ben/projects/maress
git pull

cd /home/ben/projects/maress/backend
uv sync
bash scripts/prestart.sh

cd /home/ben/projects/maress/frontend
pnpm install --frozen-lockfile
VITE_API_V1_URL=/api/v1 pnpm run build

sudo systemctl restart maress-backend
sudo systemctl restart maress-worker
sudo systemctl reload caddy
```
