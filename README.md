# ResolveDesk

ResolveDesk is a single-workspace customer support platform for managing support tickets from intake to resolution.

The current release provides a complete workflow for three roles:

- `CUSTOMER` creates tickets, follows their progress, and sends public replies.
- `AGENT` works from the service queue, claims tickets, replies to customers, and adds internal notes.
- `ADMIN` manages users and roles, oversees all tickets, assigns work, closes resolved tickets, and retains an audit trail.

The first full-stack release focuses on a reliable human support workflow. AI Copilot, knowledge bases, real-time chat, attachments, SLA automation, and multi-tenant workspaces are intentionally outside the current scope.

## Features

- Ticket creation, filtering, search, server-side pagination, and detail views.
- Ticket lifecycle: open, in progress, waiting for customer, resolved, and closed.
- Public replies and role-filtered internal notes.
- Agent queue with atomic claim behavior and Admin assignment, reassignment, and unassignment.
- Role-aware dashboards and statistics.
- Admin user management with role changes, activation/deactivation, and last-active-Admin protection.
- Soft-deleted tickets with retained audit records.
- Email-based password recovery and local Mailpit support.
- OpenAPI-generated TypeScript client shared by the frontend.
- PostgreSQL, Alembic migrations, Docker Compose, Pytest, Playwright, and GitHub Actions.

## Technology Stack

- Backend: FastAPI, SQLModel, PostgreSQL, Alembic, Pydantic, JWT authentication.
- Frontend: React, TypeScript, Vite, TanStack Router, TanStack Query, TanStack Table, Tailwind CSS, and shadcn/ui.
- Local services: Docker Compose, PostgreSQL, Mailpit, Adminer, and Traefik.
- Deployment: FastAPI Cloud or self-hosted Docker Compose.

## Quick Start

### Requirements

- Python 3.14 or newer
- [uv](https://docs.astral.sh/uv/)
- [Bun](https://bun.sh/)
- [Docker](https://www.docker.com/)

### Run the development stack

The tracked `.env` file contains local development defaults. Change its passwords and secret key before using the application outside a local environment.

Start PostgreSQL and Mailpit from the project root:

```bash
docker compose up -d db mailpit
```

In one terminal, prepare and run the backend:

```bash
cd backend
uv sync
uv run bash scripts/prestart.sh
uv run fastapi dev
```

In another terminal, install and run the frontend:

```bash
bun install
bun run dev
```

Open the application at <http://localhost:5173>. The backend API is available at <http://localhost:8000>, Swagger UI at <http://localhost:8000/docs>, and Mailpit at <http://localhost:8025>.

The initial local Admin account is configured by `FIRST_SUPERUSER` and `FIRST_SUPERUSER_PASSWORD` in `.env`. The environment variable names are retained for compatibility with the existing initialization script; the account is created with the `ADMIN` role.

### Run with Docker Compose

Build the images, prepare the database, and start the application:

```bash
docker compose build
docker compose run --rm backend bash scripts/prestart.sh
docker compose up -d --wait backend adminer
```

The application and API are served from <http://localhost:8000>. Adminer is available at <http://localhost:8080>, Traefik at <http://localhost:8090>, and Mailpit at <http://localhost:8025>.

## Tests and Quality Checks

Backend tests and coverage:

```bash
cd backend
uv run bash scripts/test.sh
```

Frontend checks:

```bash
bun run --filter frontend lint
bun run --filter frontend build
bun run --filter frontend test
```

The Playwright suite expects the Docker Compose stack to be running. See [frontend/README.md](./frontend/README.md) for the full browser-test workflow.

## Project Structure

```text
backend/
  app/api/          HTTP routes and dependencies
  app/models/       SQLModel entities and domain enums
  app/schemas/      API request and response models
  app/repositories/ Database queries and role-aware filtering
  app/services/     Ticket, user, statistics, and audit workflows
  tests/            Backend unit, integration, migration, and API tests
frontend/
  src/routes/       TanStack Router pages and role guards
  src/components/   Shared UI, ticket, queue, and Admin components
  src/client/       Generated OpenAPI client
  tests/             Playwright end-to-end tests
packages/react-email/
  Email source components and export tooling
```

## Documentation

- [Development guide](./development.md)
- [Backend guide](./backend/README.md)
- [Frontend guide](./frontend/README.md)
- [FastAPI Cloud deployment](./deployment.md)
- [Docker Compose deployment](./deployment-docker-compose.md)
- [System behavior specification](./SYSTEM-SPEC.md)
- [Contributing guide](./CONTRIBUTING.md)

## License

ResolveDesk is licensed under the terms of the MIT license.
