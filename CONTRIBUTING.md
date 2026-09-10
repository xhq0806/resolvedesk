# Contributing to ResolveDesk

Thank you for helping improve ResolveDesk.

## Before You Change Code

Read the [system behavior specification](./SYSTEM-SPEC.md) and the [development guide](./development.md). For changes that affect ticket behavior, roles, permissions, state transitions, migrations, or API contracts, also read the active material under `changes/active/ai-customer-support-platform/`.

Keep the current product boundaries in mind: ResolveDesk is a single-workspace human support platform. AI Copilot, multi-tenancy, real-time chat, attachments, SLA automation, and knowledge-base features require a separate product decision before implementation.

## Development

Set up the local stack by following [development.md](./development.md). Before opening a pull request, run the checks relevant to your change:

```bash
uv run prek run --all-files
```

Backend changes should include focused Pytest coverage. Frontend changes should include the relevant Playwright or component coverage, and API changes must regenerate the OpenAPI client.

## Pull Requests

Keep pull requests focused and describe:

1. The user-visible or operational behavior that changed.
2. The files and boundaries affected.
3. The tests and checks that were run.
4. Any migration, configuration, or deployment implications.

Do not commit secrets, local virtual environments, build output, coverage reports, or generated logs. Keep `uv.lock`, `bun.lock`, migrations, and generated API clients synchronized when they are part of the change.

## Automated Tools and AI

Automated tools and AI assistants are welcome when they support careful engineering work. Contributions still need human review, clear context, meaningful tests, and ownership of the resulting change.

## License

By contributing, you agree that your contributions are licensed under the project's MIT license.
