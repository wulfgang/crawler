.PHONY: install install-dev lint format typecheck test test-cov clean

# Python interpreter
PYTHON = python3
UV = uv

# Project directories
SRC_DIR = src
TEST_DIR = tests

# Install the package in development mode with all optional dependencies
install:
	$(UV) pip install -e "."

# Install development dependencies
install-dev:
	$(UV) pip install -r requirements-dev.in -c constraints.txt

# Run linters
lint:
	$(UV) pip install -r requirements-dev.in -c constraints.txt
	$(UV) pip install -e "."
	black --check $(SRC_DIR) $(TEST_DIR)
	isort --check-only $(SRC_DIR) $(TEST_DIR)
	flake8 $(SRC_DIR) $(TEST_DIR)

# Format code
format:
	black $(SRC_DIR) $(TEST_DIR)
	isort $(SRC_DIR) $(TEST_DIR)

# Run type checking
typecheck:
	mypy $(SRC_DIR) $(TEST_DIR)

# Run tests
test:
	pytest -v --cov=$(SRC_DIR) --cov-report=term-missing

# Run tests with coverage report
test-cov:
	pytest --cov=$(SRC_DIR) --cov-report=html

# Clean build artifacts
clean:
	rm -rf `find . -type d -name __pycache__`
	rm -rf `find . -type d -name .mypy_cache`
	rm -rf `find . -type d -name .pytest_cache`
	rm -rf `find . -type d -name .coverage`
	rm -rf `find . -type d -name htmlcov`
	rm -rf `find . -type d -name *.egg-info`
	rm -rf `find . -type d -name build`
	rm -rf `find . -type d -name dist`

# Install pre-commit hooks
install-hooks:
	pre-commit install

# Update all dependencies
update-deps:
	$(UV) pip list --outdated | awk 'NR>2 {print $$1}' | xargs -n1 $(UV) pip install -U

# Run the crawler
run:
	$(PYTHON) -m crawler.cli

# Build the package
build:
	$(UV) pip install -e .

# Update version in both version.py and pyproject.toml
# Usage: make version VERSION=x.y.z	
version:
	@echo "Updating version in version.py and pyproject.toml..."
	@if [ -z "$(VERSION)" ]; then \
		echo "Error: VERSION variable not set. Usage: make version VERSION=x.y.z"; \
		exit 1; \
	fi
	@# Update version in version.py
	@sed -i '' 's/^__version__ = .*/__version__ = "$(VERSION)"/' src/crawler/version.py
	@# Update version in pyproject.toml
	@sed -i '' 's/^version = .*/version = "$(VERSION)"/' pyproject.toml
	@echo "Version updated to $(VERSION)"

# Run the crawler in development mode
dev:
	$(UV) pip install -e "."
	$(PYTHON) -m crawler.cli
