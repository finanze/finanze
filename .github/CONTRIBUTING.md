# Contributing to Finanze

Thanks for your interest in contributing to Finanze, the self-hosted personal
finance and net worth tracker.

## Getting Started

See the [Development](../README.md#development) section of the README for setup
instructions (backend, frontend and mobile).

## Ways to Contribute

- Report bugs using the [bug report template](ISSUE_TEMPLATE/bug_report.md).
- Request features using the [feature request template](ISSUE_TEMPLATE/feature_request.md).
- Add support for new financial entities, crypto exchanges or networks.
- Submit fixes and improvements via pull requests.

## Pull Requests

1. Fork the repository and create a branch from `develop`.
2. Follow the existing code style (`ruff format` for backend, `pnpm format` for frontend).
3. Add tests for new use cases and infrastructure adapters (`tests/` and `e2e/`).
4. Ensure `pytest` and `pnpm test` pass and there are no lint errors.
5. Open the pull request against `develop` with a clear description.

## Reporting Security Issues

Please follow the [Security Policy](SECURITY.md) for vulnerability reports.
