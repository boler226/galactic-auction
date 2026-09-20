# Galactic Auction

Високонавантажена система аукціону артефактів із конкурентними ставками
через WebSocket у реальному часі. Курс: «Розробка високонавантажених
систем на Python». Лабораторна робота №1.

Стек: **FastAPI**, **PostgreSQL**, **SQLAlchemy 2 (async)**, **Alembic**,
**Docker Compose**. Контроль якості: **Black**, **Flake8**, **pre-commit**.

Детальний опис архітектури: [docs/architecture.md](docs/architecture.md).

## Швидкий старт

```bash
# 1. Віртуальне середовище
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

# 2. Конфігурація
cp .env.example .env             # Windows: copy .env.example .env

# 3. PostgreSQL у Docker
docker compose up -d db

# 4. Міграції
alembic revision --autogenerate -m "initial schema"
alembic upgrade head

# 5. Запуск
uvicorn app.main:app --reload
```

Після запуску:

- Swagger UI: http://127.0.0.1:8000/docs
- Liveness: http://127.0.0.1:8000/health
- Readiness (перевірка БД): http://127.0.0.1:8000/health/db
- WebSocket: `ws://127.0.0.1:8000/ws/auctions/1`

Повний запуск застосунку разом із БД у Docker: `docker compose up --build`.

## Контроль якості коду

```bash
pre-commit install               # один раз після клонування
pre-commit run --all-files       # ручна перевірка всього коду
black .                          # форматування
flake8 .                         # лінтер
pytest                           # тести
```

Після `pre-commit install` кожен `git commit` автоматично запускає
перевірки; коміт із синтаксичними помилками або порушенням стилю
буде заблоковано.

## Структура

```
.
├── app/
│   ├── api/routes/      # health, websocket
│   ├── core/config.py   # налаштування з .env
│   ├── db/              # engine, сесії, Base
│   ├── models/          # User, Artifact, Auction, Bid
│   └── main.py
├── alembic/             # міграції
├── docs/                # документація
├── tests/
├── docker-compose.yml
├── Dockerfile
├── .flake8
├── .pre-commit-config.yaml
└── pyproject.toml       # конфіг Black, pytest
```
