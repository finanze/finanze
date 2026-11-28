# Contributing to Finanze

Thanks for your interest in contributing to **Finanze**, the self-hosted personal finance and net worth tracker!

## Getting Started

See the [Development](../README.md#development) section of the README for complete setup instructions (backend, frontend, and mobile).

## Ways to Contribute

- **Report bugs:** Use the [bug report template](ISSUE_TEMPLATE/bug_report.md).
- **Request features:** Use the [feature request template](ISSUE_TEMPLATE/feature_request.md).
- **Add connectors:** Add support for new banks, financial entities, crypto exchanges, or blockchain networks.
- **Improve codebase:** Submit fixes, refactors, and performance improvements via Pull Requests.

---

## Contributor License Agreement (CLA)

By contributing to Finanze, you agree that your contributions will be licensed under the project's [AGPLv3 License](../LICENSE) and terms described in our [Contributor License Agreement (CLA)](../CLA.md).

- **Automated Signing:** When you open your first Pull Request, our automated **CLA Assistant bot** will leave a comment asking you to agree to the CLA. It only takes one click using your GitHub account.

---

## Pull Request Guidelines

1. **Branching:** Fork the repository and create a descriptive branch from `develop` (e.g., `feature/super-cool` or `bugfix/sync-error`).
2. **Code Style & Formatting:**
    - **Backend:** Run `ruff format` and `ruff check`.
    - **Frontend / Mobile:** Run `pnpm format` and `pnpm lint`.
    - More on this in [README.md](../README.md).
3. **Testing:**
    - Add unit tests or integration tests for new features and infrastructure adapters in `tests/` and `e2e/` if possible.
    - Ensure all tests pass: `pytest` (backend) and `pnpm test` (frontend).
    - More on this in [README.md](../README.md).
4. **Sign the CLA:** Ensure you have accepted the CLA via the automated PR bot.
5. **Submit:** Open the Pull Request against the `develop` branch with a clear title and description of your changes.

### Database migrations

Append migrations to the [registry](../finanze/infrastructure/repository/db/version_registry.py) and give each one a unique, permanent name. New names do not need an app version prefix. Never rename or remove published migrations, or reorder them within a release line. Cloud backups carry `schema_revision` (the number of registered migrations, not the SQLite migration row ID) and `schema_hash` (SHA-256 over the sorted migration names).

---

## Reporting Security Issues

Please **do not** open public GitHub issues for security vulnerabilities. Instead, follow our [Security Policy](SECURITY.md) to report them responsibly.
