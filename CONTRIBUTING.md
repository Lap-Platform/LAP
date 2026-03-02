# Contributing to LAP

Thanks for your interest in contributing! Here's how to get started.

## Setup

```bash
git clone https://github.com/Lean-Agent-Protocol/lap.git
cd lap
pip install -e ".[dev]"
```

## Running Tests

```bash
python3 -m pytest tests/ -q
```

## Code Style

- Python 3.10+
- Keep functions focused and well-typed
- Add docstrings to public functions
- Follow existing patterns in `src/`

## Pull Request Process

1. Fork the repo and create a feature branch from `main`
2. Make your changes with tests
3. Run the test suite — all tests must pass
4. Submit a PR with a clear description of what and why

## Reporting Issues

Open a GitHub issue with:
- What you expected
- What happened instead
- Minimal reproduction steps

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
