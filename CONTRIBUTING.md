# ZoneShield AI — Contributing Guide

Thank you for your interest in contributing to ZoneShield AI! This document
outlines how to get started, report issues, and submit pull requests.

## Getting Started

1. **Fork** the repository and clone your fork.
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Install dependencies: `pip install -r requirements.txt`
4. Install dev dependencies: `pip install pytest pytest-asyncio ruff mypy`
5. Run the self-check: `python -m zoneshield.selfcheck`
6. Run the test suite: `python -m pytest vision/tests/ -v`

## Reporting Issues

Before filing a new issue, please search existing issues to avoid duplicates.
When reporting a bug, include:

* Steps to reproduce the issue
* Expected behavior
* Actual behavior
* Your OpenCV version (`cv2.__version__`)
* Your platform and architecture (`platform.machine()`)
* Self-check output (`python -m zoneshield.selfcheck`)
* Any relevant benchmark or evaluation reports

## Pull Request Guidelines

1. Ensure all tests pass locally.
2. Run linters: `ruff check .` and `mypy vision/`
3. Update documentation if your change affects behavior.
4. Add tests for new functionality.
5. Follow existing code style and patterns.
6. Provide a clear description of the change in your PR.

## Competition Context

ZoneShield AI is an entry in the **OpenCV AI Competition 2026, powered by AWS**.
Contributions may be reviewed against competition rules before being merged.
See the README for more information about the competition scope and rules.

## License

By contributing, you agree that your contributions will be licensed under the
MIT License.