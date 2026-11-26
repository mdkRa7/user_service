# user_service

Сервис пользователей для кондитерской Sweet Story / Torty: регистрация, вход, JWT в cookie, подтверждение email и профиль. Написан на FastAPI. Работает вместе с `shop_service` и фронтендом на Next.js.

## Возможности

- Регистрация с хешированием паролей (Argon2)
- Подтверждение email по 6-значному коду (можно отключить)
- Вход, выход и обновление токена: JWT (RS256) в `httpOnly` cookie
- Роли `user` и `admin`, роль зашита в JWT
- Лимиты запросов на вход, регистрацию и подтверждение (slowapi + Redis)
- Суточная квота на отправку писем и демо-режим без реальной почты
- Cloudflare Turnstile (капча, необязательно)
- Миграции базы через Alembic

## Стек

Python 3.13 · FastAPI · SQLAlchemy 2 (async) + asyncpg · PostgreSQL · Redis · Alembic · PyJWT · Poetry · Docker

## Структура

```
app/
  main.py                     вход в приложение
  api/v1/endpoints/           auth, user, healthcheck
  core/                       config, security (JWT), limiter, captcha
  domain/                     сервисы и enum ролей
  infrastructure/             БД (модели, crud), клиенты Redis и почты
  schemas/                    Pydantic-схемы
alembic/                      миграции
keys/                         JWT-ключи (в Git не попадают)
Dockerfile, docker-compose.yaml
```

## API

Все маршруты начинаются с `/v1`.

| Метод | Путь | Описание |
|---|---|---|
| GET | `/v1/healthcheck` | Проверка, что сервис жив |
| POST | `/v1/auth/register` | Регистрация. С подтверждением email вернёт `verification_required: true` |
| POST | `/v1/auth/verify-email` | Подтверждение кода (если включено) |
| POST | `/v1/auth/login` | Вход, ставит cookie `access_token` и `refresh_token` |
| POST | `/v1/auth/refresh` | Обновление токенов по `refresh_token` |
| POST | `/v1/auth/logout` | Выход, удаляет cookie |
| GET | `/v1/user/me` | Текущий пользователь (id, email, роль) |

Интерактивная документация: `/docs` (Swagger).

## Локальный запуск через Docker

1. Создайте JWT-ключи (папка `keys/` в Git не хранится):

   ```bash
   mkdir keys
   openssl genrsa -out keys/private.pem 2048
   openssl rsa -in keys/private.pem -pubout -out keys/public.pem
   ```

2. Скопируйте шаблон и заполните:

   ```bash
   cp .env.docker.template .env.docker
   ```

3. Запустите сервис с Postgres и Redis:

   ```bash
   docker compose up -d --build
   docker compose exec app alembic upgrade head
   ```

4. Проверка:

   ```bash
   curl http://127.0.0.1:8005/v1/healthcheck
   ```

Порты локально: сервис — `8005`, Postgres — `5436`, Redis — `6379`.

## Локальный запуск без Docker

```bash
poetry install
cp .env.template .env      # заполните значения
cd app
alembic upgrade head       # из корня проекта, где лежит alembic.ini
uvicorn main:app --reload --port 8005
```

## Переменные окружения

Все переменные имеют префикс `CONFIG__`, вложенность задаётся через `__`.

| Переменная | Описание |
|---|---|
| `CONFIG__DB__URL` | Строка подключения к Postgres, формат `postgresql+asyncpg://user:pass@host:5432/db` |
| `CONFIG__REDIS__URL` | Строка Redis: `redis://...` или `rediss://...` (с TLS) |
| `CONFIG__JWT__PRIVATE_KEY_PATH` | Путь к приватному ключу (относительно корня проекта или абсолютный) |
| `CONFIG__JWT__PUBLIC_KEY_PATH` | Путь к публичному ключу |
| `CONFIG__AUTH__EMAIL_VERIFICATION` | `true` — код на email, `false` — аккаунт создаётся сразу |
| `CONFIG__DEMO__ENABLED` | `true` — письма не отправляются, код фиксированный |
| `CONFIG__DEMO__CODE` | Фиксированный код в демо-режиме |
| `CONFIG__DEMO__FALLBACK_ON_QUOTA` | При исчерпании суточной квоты писем вернуть демо-код вместо ошибки |
| `CONFIG__MAIL__PROVIDER` | `smtp` или `mailtrap_api` |
| `CONFIG__MAIL__USERNAME`, `CONFIG__MAIL__PASSWORD` | Доступ к SMTP |
| `CONFIG__MAIL__API_TOKEN` | Токен для `mailtrap_api` |
| `CONFIG__MAIL__DAILY_LIMIT` | Суточная квота писем (по умолчанию 120) |
| `CONFIG__COOKIE__SECURE` | `true` на HTTPS (в продакшене обязательно) |
| `CONFIG__COOKIE__SAMESITE` | `lax` (по умолчанию) |
| `CONFIG__CORS__ORIGINS` | Список origin через запятую; нужен, только если фронтенд обращается к API напрямую |
| `CONFIG__TURNSTILE__ENABLED`, `CONFIG__TURNSTILE__SECRET` | Капча Cloudflare |

Файлы `.env`, `.env.docker` и папка `keys/` не должны попадать в Git.

## Redis

Redis используется как кэш и хранилище:
- счётчики лимитов запросов (общие для всех процессов, переживают перезапуск);
- коды подтверждения email;
- суточная квота писем.

Без Redis сервис не запустится.

## Деплой (Northflank)

1. Репозиторий на GitHub, ветка с кодом. В проекте Northflank создайте **Combined service** с билдом из `Dockerfile`, публичным HTTP-портом **8000**.
2. База: PostgreSQL addon. В `CONFIG__DB__URL` используйте драйвер `postgresql+asyncpg://`. Если база требует TLS, добавьте `?ssl=require`.
3. Redis: например, Upstash (`rediss://...`) или Redis addon.
4. JWT-ключи в образ не попадают. Добавьте их как **Secret files** (секретные файлы) в service или secret group и смонтируйте по абсолютным путям, например `/run/secrets/private.pem` и `/run/secrets/public.pem`, затем укажите эти пути в `CONFIG__JWT__PRIVATE_KEY_PATH` и `CONFIG__JWT__PUBLIC_KEY_PATH`.
5. Для HTTPS включите `CONFIG__COOKIE__SECURE=true`.
6. Выполните миграции один раз (job с командой `alembic upgrade head`).
7. Проверьте `https://<адрес-сервиса>/v1/healthcheck`.

Публичный ключ нужен и `shop_service`: он проверяет JWT, а приватный ключ хранится только здесь.

## Как назначить администратора

Эндпоинта для этого нет, роль меняется в базе. После регистрации нужного пользователя выполните SQL:

```sql
UPDATE users SET role = 'admin' WHERE email = 'admin@example.com';
```

Новая роль попадёт в токен после следующего входа.

## Безопасность

- Пароли хранятся только в виде хеша Argon2.
- Токены лежат в `httpOnly` cookie, JavaScript на странице их не видит.
- Приватный JWT-ключ и файлы `.env*` не хранятся в Git.
- Лимиты запросов определяют IP клиента за прокси по заголовкам `cf-connecting-ip`, `x-real-ip`, `x-forwarded-for`, поэтому сервис нельзя открывать в интернет в обход прокси без проверки.