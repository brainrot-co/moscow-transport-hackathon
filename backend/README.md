# FastAPI JWT Auth

Production-oriented JWT authentication service built with FastAPI, PostgreSQL, and Redis.

Implements secure JWT authentication with access/refresh token rotation, Redis-backed refresh token revocation, Role-Based Access Control (RBAC), and a fully async, layered architecture designed for scalability and maintainability.

## What Is Implemented

- FastAPI app with versioned API prefix: `/api/v1`
- JWT authentication:
  - Access token in response body
  - Refresh token in `HttpOnly` cookie
- Refresh token rotation with one-time use semantics via Redis `GETDEL`
- Role-Based Access Control (RBAC):
  - User role embedded into JWT access tokens
  - Hierarchical role levels (`user` < `admin`)
  - Role-based endpoint protection via the `RequireRole` dependency
- Password hashing with Argon2 (Passlib)
- Async SQLAlchemy 2.0 + asyncpg
- Alembic migration setup (async)
- Infrastructure lifecycle managed via FastAPI `lifespan` and `app.state`
- Dependency injection with typed CRUD protocols
- Centralized exception handling
- Rate limiting (SlowAPI)
- CORS middleware configuration
- Liveness / readiness health probes
- Automated CI/CD pipelines (GitHub Actions)

## Tech Stack

- Python 3.12+
- FastAPI
- SQLAlchemy (async)
- PostgreSQL (asyncpg)
- Redis
- Alembic
- PyJWT
- Passlib (argon2)
- Pydantic Settings
- SlowAPI (rate limiting)
- Ruff, Mypy, and Black (linting & formatting)
- Pytest (unit tests)
- Docker & Docker Compose
- GitHub Actions (CI/CD)

## Architecture

The project follows a layered architecture with clear separation of concerns:

```
API (endpoints) -> Services (business logic) -> CRUD (data access) -> Models
```

- **Endpoints** are thin and delegate to services.
- **Services** contain business logic and depend on CRUD via a `Protocol`
  (`app/protocols/user.py`), which keeps them decoupled and easy to test.
- **CRUD** performs data access only; transaction commit/rollback is centralized
  in the database session dependency.
- **Infrastructure** (database engine, Redis client) is created once on startup
  in `app/lifespan.py`, stored on `app.state`, and accessed through dependencies.

## Project Structure

```text
.
|- alembic/
|  |- env.py
|  |- versions/
|- app/
|  |- main.py              # App factory, middleware, routers
|  |- lifespan.py          # Startup/shutdown: db & redis clients on app.state
|  |- api/
|  |  |- health.py         # Liveness / readiness probes
|  |  |- v1/
|  |  |  |- router.py
|  |  |  |- endpoints/     # auth, users
|  |- auth/                # Auth dependencies, RBAC permissions, token schema
|  |- core/                # Config, security, constants, limiter, logger
|  |- crud/                # Data access layer
|  |- db/                  # DatabaseClient (postgres), RedisClient
|  |- dependencies/        # DI: db session, redis, crud, services
|  |- enums/               # Role enum with hierarchical levels
|  |- exceptions/          # Custom exceptions + handlers
|  |- models/              # SQLAlchemy models
|  |- protocols/           # Typed CRUD protocols for DI
|  |- schemas/             # Pydantic schemas
|  |- services/            # Business logic (user, auth)
|  |- utils/               # Helpers (cookie handling)
|- tests/
|  |- fakes/
|  |- unit/
|- .env.template
|- alembic.ini
|- docker-compose.yml       # Local development
|- docker-compose.prod.yml  # Production
|- Dockerfile
|- Makefile
|- poetry.lock
|- pyproject.toml
|- pytest.ini
|- README.md
```

## Authentication Flow

1. Register a user (`POST /api/v1/register`)
2. Login (`POST /api/v1/login`)
3. Receive:
   - `access_token` in the JSON response
   - `refresh_token` in a secure `HttpOnly` cookie
4. Use the access token for protected endpoints (Bearer auth)
5. The access token carries authenticated user information, including the assigned role
6. Protected endpoints enforce role-based authorization via `RequireRole`
7. Refresh the access token (`POST /api/v1/refresh`) using the refresh cookie
   (the old refresh token is rotated and invalidated)
8. Logout (`POST /api/v1/logout`) revokes the refresh token in Redis and clears the cookie

## API Endpoints

Auth and user endpoints are under `/api/v1`. Health endpoints are top-level.

| Method | Path | Auth | Rate Limit | Description |
|---|---|---|---|---|
| GET | `/health/live` | No | - | Liveness probe |
| GET | `/health/ready` | No | - | Readiness probe (checks Postgres + Redis) |
| POST | `/api/v1/register` | No | 1/min | Register a new user |
| POST | `/api/v1/login` | No | 5/min | Login with username/password form |
| POST | `/api/v1/refresh` | No | 3/min | Rotate refresh token and issue a new access token |
| POST | `/api/v1/logout` | No | 3/min | Revoke the current refresh token and clear the cookie |
| GET | `/api/v1/about_me` | Bearer (`user`) | - | Get the current authenticated user |

## Configuration

Configuration is loaded from a `.env` file via Pydantic Settings.

| Variable | Required | Notes |
|---|---|---|
| `DEBUG` | No | `true` or `false` (default `false`) |
| `CORS_ORIGINS` | No | JSON array of allowed origins |
| `POSTGRES_DB` | Yes* | Used by Docker Compose to init the database |
| `POSTGRES_USER` | Yes* | Used by Docker Compose to init the database |
| `POSTGRES_PASSWORD` | Yes* | Used by Docker Compose to init the database |
| `DATABASE_URL` | Yes | Must start with `postgresql+asyncpg://` or `postgres+asyncpg://` |
| `REDIS_URL` | Yes | Must start with `redis://` or `rediss://` |
| `ACCESS_SECRET` | Yes | Min length: 32; must not start with `CHANGE_ME` |
| `REFRESH_SECRET` | Yes | Min length: 32; must not start with `CHANGE_ME` |
| `ACCESS_TOKEN_EXPIRE_M` | No | Access token lifetime in minutes (default: `15`) |
| `REFRESH_TOKEN_EXPIRE_M` | No | Refresh token lifetime in minutes (default: `43200`) |
| `COOKIE_SECURE` | No | Default: `true` |
| `COOKIE_SAMESITE` | No | One of `lax`, `strict`, `none` |

\* Required only when running via Docker Compose.

Notes:

- The app validates configuration on startup and refuses to run with missing,
  malformed, or default (`CHANGE_ME...`) secrets.
- For local HTTP development without HTTPS, set `COOKIE_SECURE=false`, otherwise
  the browser/client may not send the refresh cookie and `/refresh` / `/logout`
  can fail with `401`.

## Quick Start (Docker Compose)

This is the recommended way to run the project locally. Service hostnames
(`db`, `redis`) resolve inside the Docker network.

### 1. Create the environment file

```bash
cp .env.template .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.template .env
```

Then edit `.env` and set real values (secrets, database credentials).

### 2. Start the services

```bash
docker compose up --build
```

### 3. Run database migrations

```bash
docker compose run --rm app alembic upgrade head
```

Makefile shortcuts:

```bash
make up
make down
make migrate
make makemigrations m="describe change"
make logs
```

Once running, open:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

### Production

A dedicated compose file is provided for production (e.g., on a VPS). It pulls a
prebuilt image and reads secrets from a server-side `.env`:

```bash
docker compose -f docker-compose.prod.yml up -d
```

Deployment is automated via GitHub Actions (`.github/workflows/cd.yml`): on a
successful CI run against `main`, the image is built, pushed to GHCR, migrations
are applied, and the stack is redeployed.

## Local Development (without Docker)

If you prefer running the app directly on your host, you need local PostgreSQL
and Redis instances, and `.env` hostnames pointing to `localhost`.

### 1. Prerequisites

- Python 3.12+
- Poetry 2.0+
- PostgreSQL
- Redis

### 2. Install Poetry

```bash
pipx install poetry
```

### 3. Install dependencies

```bash
poetry install --with dev
```

Tip: run `poetry shell` once, then run commands without the `poetry run` prefix.

### 4. Configure environment

Create `.env` from the template and point `DATABASE_URL` / `REDIS_URL` to
`localhost`.

### 5. Run migrations and start the app

```bash
poetry run alembic upgrade head
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Testing

Run all tests:

```bash
poetry run pytest
```

Run only unit tests:

```bash
poetry run pytest tests/unit
```

## Development Tools

Format code with Black:

```bash
poetry run black .
```

Lint code with Ruff:

```bash
poetry run ruff check .
```

Check types with Mypy:

```bash
poetry run mypy app
```

## Request Examples

### Register

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/register" \
  -H "Content-Type: application/json" \
  -d '{"username":"john_doe","email":"john@example.com","password":"StrongPass123"}'
```

### Login (stores the refresh cookie into a file)

```bash
curl -i -X POST "http://127.0.0.1:8000/api/v1/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -c cookies.txt \
  -d "username=john_doe&password=StrongPass123"
```

### Refresh

```bash
curl -i -X POST "http://127.0.0.1:8000/api/v1/refresh" \
  -b cookies.txt \
  -c cookies.txt
```

### About Me

```bash
curl -X GET "http://127.0.0.1:8000/api/v1/about_me" \
  -H "Authorization: Bearer <access_token>"
```

### Logout

```bash
curl -i -X POST "http://127.0.0.1:8000/api/v1/logout" \
  -b cookies.txt \
  -c cookies.txt
```

## Error Model

Application-specific errors use this shape:

```json
{"detail": "..."}
```

Common statuses:

- `201` Created (register)
- `200` OK (login, refresh, logout, about_me)
- `401` Unauthorized (invalid credentials/token)
- `403` Forbidden (insufficient role)
- `404` Not Found (user not found)
- `409` Conflict (user already exists)
- `429` Too Many Requests (rate limit exceeded)

## Migrations

Create a migration:

```bash
poetry run alembic revision --autogenerate -m "describe change"
```

Upgrade the database:

```bash
poetry run alembic upgrade head
```

Downgrade one revision:

```bash
poetry run alembic downgrade -1
```
