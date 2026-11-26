# Contributing to Aesthetic Wallpapers

Thank you for your interest in contributing! This guide covers both adding wallpapers and working on the Python utilities.

## Table of Contents

- [Adding Wallpapers](#adding-wallpapers)
- [Python Development](#python-development)
  - [Environment Setup](#environment-setup)
  - [Code Style](#code-style)
  - [Testing](#testing)
  - [Submitting a Pull Request](#submitting-a-pull-request)

---

## Adding Wallpapers

1. Fork the repository and create a new branch.
2. Place your wallpaper in the `aesthetic-wallpapers/` directory.
3. Supported formats: `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp`, `.tiff`.
4. Verify the image with the processor before opening a PR:
   ```bash
   python wallpaper_processor.py info aesthetic-wallpapers/
   ```
5. Open a pull request with a short description of the image.

---

## Python Development

### Environment Setup

Requires **Python 3.10+**.

```bash
# Clone the repository
git clone https://github.com/SaOYaD-SZN/Aesthetic-Wallpapers.git
cd Aesthetic-Wallpapers

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install development dependencies
pip install -r requirements-dev.txt
```

### Code Style

This project uses:

| Tool | Purpose | Command |
|------|---------|---------|
| [Black](https://black.readthedocs.io/) | Formatting | `black .` |
| [isort](https://pycqa.github.io/isort/) | Import sorting | `isort .` |
| [flake8](https://flake8.pycqa.org/) | Linting | `flake8 *.py tests/` |
| [mypy](https://mypy.readthedocs.io/) | Type checking | `mypy *.py` |

Run all formatters at once:

```bash
black . && isort .
```

### Testing

```bash
# Run the full test suite
pytest

# Run with coverage report
pytest --cov=. --cov-report=term-missing

# Run a specific test file
pytest tests/test_star_repos.py -v
```

All public functions must have:
- Type annotations for every parameter and return value.
- A docstring following [Google style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).
- At least one unit test.

### Submitting a Pull Request

1. Branch off `main` with a descriptive name: `feature/my-feature` or `fix/bug-description`.
2. Write or update tests as needed.
3. Run the full lint + test suite locally:
   ```bash
   black --check . && isort --check-only . && flake8 *.py tests/ && mypy *.py && pytest
   ```
4. Open a PR against `main`. The CI pipeline will run automatically.
5. Describe **what** you changed and **why** in the PR description.

---

## Code of Conduct

Be respectful and constructive. All contributions are welcome!
