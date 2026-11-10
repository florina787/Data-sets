# Contributing to VEENA.AI

Thank you for helping. VEENA is open source under the [GPL-3.0](LICENSE).

## Ways to help

- **Report a bug or idea:** [GitHub Issues](https://github.com/florina787/Data-sets/issues). Include your OS, the VEENA version and steps to reproduce.
- **Security problems:** please follow [SECURITY.md](SECURITY.md) instead of opening an issue.
- **Code and documentation:** pull requests are welcome.

## Develop

See **Develop** in the [README](README.md#develop) for setup. Before opening a pull request, run:

```bash
ruff check backend tests packaging && ruff format --check backend tests
pytest -m "not ollama and not asr and not embeddings"
cd apps/desktop && npm run typecheck && npm run lint && npm test
```

If you change behaviour that depends on a model, also run the real-model suites (`pytest -m "ollama or asr or embeddings"`) and the end-to-end tests (`npx playwright test`). They need Ollama with the models named in the tests.

## Principles

- **Local first.** Nothing leaves the user's computer without explicit consent.
- **No invented claims.** Numbers in docs and on the website must come from measurements in this repository.
- **Recommended models must allow commercial use.** A test enforces this.
- **Capture stays visible and user-started.** No covert recording or covert interview assistance.

By contributing, you agree that your contribution is licensed under the GPL-3.0.
