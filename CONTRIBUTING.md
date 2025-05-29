# Contributing to NexusMind

We welcome contributions to NexusMind! Please follow these general guidelines when contributing:

## Development Process

1.  **Fork the Repository:** Start by forking the main NexusMind repository.
2.  **Create a Branch:** Create a new branch for your feature or bug fix:
    ```bash
    git checkout -b feature/your-feature-name
    ```
    or
    ```bash
    git checkout -b bugfix/issue-number
    ```
3.  **Install Dependencies:** Ensure you have [Poetry](https://python-poetry.org/) installed and run:
    ```bash
    poetry install --with dev
    ```
4.  **Make Changes:** Implement your feature or bug fix.
5.  **Write Tests:** Add appropriate tests for your changes. Ensure existing tests pass.
    ```bash
    poetry run pytest
    ```
6.  **Check Code Quality:** Run linters and type checkers:
    ```bash
    poetry run ruff check .
    poetry run ruff format .
    poetry run mypy src/
    ```
7.  **Commit Your Changes:** Follow conventional commit guidelines if possible.
8.  **Submit a Pull Request:** Push your branch to your fork and submit a pull request to the main NexusMind repository. Provide a clear description of your changes.

## Code Style

*   Follow PEP 8 style guidelines.
*   Use type hints for all functions and methods.
*   Write comprehensive docstrings.
*   Aim to maintain or increase test coverage.

## Reporting Issues

If you find a bug or have a feature request, please open an issue on the GitHub repository.

Thank you for contributing!
