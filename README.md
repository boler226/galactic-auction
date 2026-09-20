# Galactic Auction

Високонавантажена система аукціону артефактів із конкурентними ставками
через WebSocket у реальному часі. Курс: «Розробка високонавантажених
систем на Python».

- **Лабораторна №1:** архітектура, каркас, БД, контроль якості коду.
- **Лабораторна №2:** користувачі, ролі, JWT-автентифікація, розмежування
  доступу, MVP аукціону, тести.

Стек: **FastAPI**, **PostgreSQL**, **SQLAlchemy 2 (async)**, **Alembic**,
**JWT (PyJWT)**, **bcrypt**, **pytest**. Контроль якості: **Black**,
**Flake8**, **pre-commit**.

Документація:
[архітектура](docs/architecture.md) ·
[авторизація та ролі (Лаба 2)](docs/lab2-auth-architecture.md)

## Швидкий старт

```bash
# 1. Віртуальне середовище
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# 2. Конфігурація
cp .env.example .env             # Windows: copy .env.example .env
# у .env задайте власний SECRET_KEY:
#   python -c "import secrets; print(secrets.token_urlsafe(48))"

# 3. PostgreSQL у Docker
docker compose up -d db

# 4. Міграції
alembic upgrade head

# 5. Адміністратор і демо-дані
python -m app.cli create-admin --username admin --email admin@example.com
python -m app.cli seed-demo      # admin, alice, bob, артефакти, 1 аукціон

# 6. Запуск
uvicorn app.main:app --reload
```

Swagger UI: http://127.0.0.1:8000/docs. Кнопка **Authorize** приймає
`username` і `password`, після чого захищені маршрути викликаються прямо
зі Swagger.

## Ролі та доступ

| Роль | Можливості |
|---|---|
| Анонім | Реєстрація, вхід, перегляд артефактів і аукціонів |
| `user` | Свій профіль, поповнення балансу, ставки, `/home/user` |
| `admin` | Все з адмін-панелі, артефакти, аукціони, закриття торгів, `/home/admin` |

Публічна реєстрація створює лише `user`. Адміністратор створюється
командою `python -m app.cli create-admin`. Повна матриця доступу:
[docs/lab2-auth-architecture.md](docs/lab2-auth-architecture.md).

## Основні ендпоінти

| Метод і шлях | Опис |
|---|---|
| `POST /auth/register` | Реєстрація користувача |
| `POST /auth/login` | Вхід, повертає JWT |
| `GET /users/me` | Мій профіль |
| `GET/PATCH /users/{id}` | Профіль (свій, або будь-який для admin) |
| `POST /users/{id}/deposit` | Поповнення балансу |
| `GET /home/user`, `GET /home/admin` | Домашні сторінки-заглушки |
| `GET /admin/users`, `/admin/stats`, `PATCH /admin/users/{id}` | Адмін-панель |
| `POST /artifacts`, `POST /auctions`, `POST /auctions/{id}/close` | Керування лотами (admin) |
| `POST /auctions/{id}/bids` | Ставка (user) |
| `WS /ws/auctions/{id}?token=<JWT>` | Події аукціону в реальному часі |

## Тести та якість коду

```bash
pytest                           # 92 тести, Docker не потрібен
pytest -v                        # докладний вивід
pre-commit install               # один раз після клонування
pre-commit run --all-files
```

## Демонстрація захисту від race condition

```bash
# сервер має працювати
python scripts/bid_race_demo.py --admin-password "Admin12345!" --bidders 20
```

Скрипт створює аукціон, реєструє N користувачів і змушує їх зробити
ставки одночасно, а потім перевіряє, що найвища ставка не загубилась.

## Структура

```
.
├── app/
│   ├── api/
│   │   ├── deps.py          # автентифікація та авторизація
│   │   └── routes/          # auth, users, home, admin, artifacts, auctions, ws
│   ├── core/                # config, security (bcrypt, JWT)
│   ├── db/                  # engine, сесії, Base
│   ├── models/              # User, Artifact, Auction, Bid
│   ├── schemas/             # Pydantic-схеми
│   ├── services/            # бізнес-логіка (users, auctions, bidding)
│   ├── cli.py               # create-admin, seed-demo
│   ├── realtime.py          # WebSocket-кімнати
│   └── main.py
├── alembic/                 # міграції
├── docs/                    # документація
├── scripts/                 # bid_race_demo.py
├── tests/
├── docker-compose.yml
└── pyproject.toml           # Black, pytest
```
