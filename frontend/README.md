# ResolveDesk Frontend

The frontend is a React single-page application for the ResolveDesk customer, agent, and admin workflows. It uses Vite, TypeScript, TanStack Router, TanStack Query, TanStack Table, Tailwind CSS, shadcn/ui, and the generated OpenAPI client.

## Requirements

- [Bun](https://bun.sh/)
- A running ResolveDesk backend for API requests

## Local Development

From the project root:

```bash
bun install
bun run dev
```

Open <http://localhost:5173>. The Vite development server uses `VITE_API_URL` from `frontend/.env`, which defaults to `http://localhost:8000`.

Start PostgreSQL and Mailpit, then prepare and run the backend in a separate terminal. The complete workflow is documented in [../development.md](../development.md).

## Role-Based Application Areas

- Customers use `/tickets` to create, filter, search, and reply to their own tickets.
- Agents use `/queue` to view unassigned work, claim tickets, reply, add internal notes, and update tickets they own.
- Admins use `/admin/tickets` for global ticket management and `/admin` for user, role, and account-status management.
- All authenticated users share the dashboard and account settings pages.

Route guards are enforced in the frontend for navigation ergonomics. The backend remains the source of truth for authorization and resource-level access.

## Build and Serve from FastAPI

Build the frontend from `frontend/`:

```bash
bun run build
```

The build is written to `backend/app/frontend` and is served by FastAPI at <http://localhost:8000>.

## Generate the API Client

The client is generated from the backend OpenAPI contract. Regenerate it whenever a backend API change affects the schema:

```bash
bash ./scripts/generate-client.sh
```

Commit the generated changes under `frontend/src/client/` and `frontend/.generated-client/` when that directory is present in the local workflow. Do not maintain a second hand-written API client.

For a manual generation workflow, start the backend, download `/api/v1/openapi.json` to `frontend/openapi.json`, and run:

```bash
bun run generate-client
```

## Code Structure

- `src/routes/` contains file-based routes, URL filter state, and role guards.
- `src/components/Tickets/` contains ticket lists, detail views, timelines, replies, actions, and statistics.
- `src/components/Admin/` contains user management views.
- `src/components/Common/` contains shared layout and table primitives.
- `src/lib/` contains query options, cache keys, and shared utilities.
- `src/client/` contains the generated OpenAPI client.
- `tests/` contains Playwright end-to-end tests for authentication, role navigation, tickets, queues, and user management.

## Linting, Build, and End-to-End Tests

Run frontend checks from the project root:

```bash
bun run --filter frontend lint
bun run --filter frontend build
```

For Playwright tests, start the Compose stack first:

```bash
docker compose build
docker compose run --rm backend bash scripts/prestart.sh
docker compose up -d --wait backend
```

Then run the browser suite:

```bash
bun run --filter frontend test
bun run --filter frontend test:ui
```

To stop the test stack and remove its data:

```bash
docker compose down -v
```
