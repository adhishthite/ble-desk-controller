.PHONY: install format lint check clean chat help

# Default target
help:
	@echo "Available commands:"
	@echo "  make install  - Install dependencies"
	@echo "  make format   - Format code with ruff"
	@echo "  make lint     - Lint code with ruff"
	@echo "  make check    - Run format + lint"
	@echo "  make clean    - Remove cache and build artifacts"
	@echo "  make chat     - Run interactive desk chat agent"

# Install dependencies
install:
	uv sync

# Format code
format:
	uv run ruff format .

# Lint code (with auto-fix)
lint:
	uv run ruff check . --fix

# Check = format + lint
check: format lint

# Run chat agent
chat:
	uv run desk-chat

# Clean artifacts
clean:
	rm -rf __pycache__ .ruff_cache .pytest_cache
	rm -rf *.egg-info dist build
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
