# Лабораторна №5: контейнеризація (Docker)

## Архітектура

| Сервіс | Образ | Порт на хості | Мережа | Дані |
|---|---|---|---|---|
| `app-sandbox` | `galactic-auction` (Dockerfile) | 8000 | `sandbox_net` | немає стану |
| `db-sandbox` | `postgres:16-alpine` | 5434 | `sandbox_net` | том `pgdata_sandbox` |
| `app-production` (profile) | `galactic-auction` | 8001 | `production_net` | немає стану |
| `db-production` (profile) | `postgres:16-alpine` | 5433 | `production_net` | том `pgdata_production` |

- Dockerfile двоетапний: етап `builder` ставить залежності у virtualenv, етап `runtime`
  містить лише venv і код. Контейнер працює від непривілейованого користувача.
- Env-файли (`.env.sandbox`, `.env.production`) не потрапляють в образ
  (`.dockerignore`), compose передає їх під час запуску через `env_file`.
- Усередині контейнера база доступна за іменем сервісу на порту 5432, тому
  `POSTGRES_HOST`/`POSTGRES_PORT` перевизначені в `environment`.
- Sandbox і production живуть у різних мережах і не бачать одне одного.
- `depends_on` з `condition: service_healthy`: застосунок стартує після того, як
  PostgreSQL пройшов `pg_isready`. Міграції (`alembic upgrade head`) виконуються
  автоматично перед стартом сервера.

## Запуск

Sandbox (за замовчуванням):

```bat
docker compose up --build
```

Production (окремий profile):

```bat
docker compose --profile production up --build
```

Фоновий режим: додати `-d`. Зупинка: `docker compose down` (дані зберігаються),
`docker compose down -v` (видаляє томи разом з даними).

Команди всередині контейнерів:

```bat
docker compose exec app-sandbox python -m app.cli seed-demo
docker compose --profile production exec app-production python -m app.cli create-admin --username admin --email admin@example.com
```

## Режим розробки з hot-reload

```bat
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Каталог `./app` змонтовано в контейнер, uvicorn запущено з `--reload`. Зміна будь-якого
файлу в `app/` перезапускає сервер без перебудови образу.

## Перевірка

| Що перевірити | Команда | Очікувано |
|---|---|---|
| Контейнери піднялись | `docker compose ps` | `healthy` для db і app |
| Міграції виконались | `docker compose logs app-sandbox` | рядки `Running upgrade ...` |
| Таблиці в БД | `docker compose exec db-sandbox psql -U auction_sandbox -d galactic_sandbox -c "\dt"` | список таблиць |
| API відповідає | http://127.0.0.1:8000 та http://127.0.0.1:8000/docs | сайт і Swagger (sandbox) |
| Production | http://127.0.0.1:8001/docs | 404 |
| Дані переживають перезапуск | створити користувача, `docker compose down`, `docker compose up -d` | користувач на місці |
| Мережа | `docker network ls` | `..._sandbox_net`, `..._production_net` |

## Розмір образу (multi-stage)

```bat
docker images galactic-auction
```

Для порівняння з одноетапною збіркою збережіть старий Dockerfile як `Dockerfile.single`:

```bat
docker build -f Dockerfile.single -t galactic-auction:single .
docker images galactic-auction
```

| Образ | Розмір |
|---|---|
| single-stage | <вписати> |
| multi-stage | <вписати> |
