# ResolveDesk Backend

The backend is a synchronous FastAPI application that serves the ResolveDesk API and, in production builds, the compiled frontend from the same origin.

## Requirements

- [Docker](https://www.docker.com/) for PostgreSQL and Mailpit.
- [uv](https://docs.astral.sh/uv/) for Python package and environment management.
- Python 3.14 or newer.

## Local Development

From the project root, start the supporting services:

```bash
docker compose up -d db mailpit
```

From `backend/`, install dependencies, apply migrations, and start the API:

```bash
uv sync
uv run bash scripts/prestart.sh
uv run fastapi dev
```

The API is available at <http://localhost:8000>. OpenAPI JSON is available at <http://localhost:8000/api/v1/openapi.json>, and Swagger UI is available at <http://localhost:8000/docs>.

## Backend Responsibilities

- `app/api/routes/` declares HTTP endpoints and maps domain errors to API responses.
- `app/models/` contains SQLModel entities and database enums.
- `app/schemas/` contains request, response, filter, and error schemas.
- `app/repositories/` owns database queries, role-aware filtering, pagination, conditional updates, and aggregates.
- `app/services/` owns ticket state transitions, permissions, user lifecycle rules, statistics, transactions, and audit records.
- `app/core/` contains configuration, authentication, database setup, request IDs, and error handling.
- `tests/` contains unit, API, migration, OpenAPI, and integration coverage.

The main business resources are users, tickets, ticket messages, and ticket audit records. `Item` is no longer part of the product or API.

## Full Stack with Docker Compose

To run the backend and the built frontend in Docker Compose:

```bash
docker compose build
docker compose run --rm backend bash scripts/prestart.sh
docker compose up -d --wait backend adminer
```

The application is available at <http://localhost:8000>. Use `docker compose exec backend bash` to open a shell in the backend container.

## Backend Tests

Run the backend checks from `backend/`:

```bash
uv run bash scripts/test.sh
```

To run tests against an already running Compose stack:

```bash
docker compose exec backend bash scripts/tests-start.sh
```

Extra Pytest arguments are forwarded:

```bash
docker compose exec backend bash scripts/tests-start.sh -x
```

Coverage output is written to `backend/htmlcov/`.

## Migrations

Create and apply an Alembic revision from `backend/` after changing a model:

```bash
uv run alembic revision --autogenerate -m "Describe the schema change"
uv run alembic upgrade head
```

Commit generated files under `app/alembic/versions/`. The current migration history includes the transition from the template's `Item` model to the ResolveDesk ticket platform and maps existing superusers to the `ADMIN` role.

## Email Templates

Email source components live in `packages/react-email/`. The rendered templates consumed by the backend live in `app/email-templates/` and should not be edited by hand.

Preview and export the templates from the project root:

```bash
bun run email:dev
bun run email:export
```

Password recovery and new-account email behavior depends on the SMTP variables described in the [development guide](../development.md).
