# Run all discovered tests in the project
pytest

# Run with verbose output (shows individual test names and pass/fail status)
pytest -v

# Run with coverage report (if pytest-cov is installed)
pytest --cov=. -v
