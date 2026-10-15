# CryptEasy developer commands.
# Requires GNU Make and uv. On Windows, run from Git Bash; install make with
# `winget install ezwinports.make` or `choco install make`, or run the uv command
# shown under each target directly.  # verify this (Windows make packages)
#
# The CI workflow (.github/workflows/ci.yml) runs the same uv commands, so keep
# the two in sync when a target changes.

PYTEST := uv run pytest
SPEC   := packaging/crypteasy.spec

.DEFAULT_GOAL := help
.PHONY: help install run lint format test test-core test-keystore test-ui test-e2e test-slow test-all build smoke clean

help: ## List available targets
	@grep -E '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-14s %s\n", $$1, $$2}'

install: ## Install locked dependencies into .venv
	uv sync --locked

run: ## Start the app and open it in the browser
	uv run python -m crypteasy

lint: ## Lint + format check (no changes); what CI runs
	uv run ruff check .
	uv run ruff format --check .

format: ## Auto-fix lint issues where safe, then format the code
	uv run ruff check --fix .
	uv run ruff format .

test: ## Fast test suite (everything except @slow); what CI runs
	$(PYTEST) -m "not slow" $(ARGS)

test-core: ## Track A: crypto engine tests
	$(PYTEST) tests/core -m "not slow" $(ARGS)

test-keystore: ## Track C: key storage and contacts tests
	$(PYTEST) tests/keystore $(ARGS)

test-ui: ## Track B: Flask routes and security middleware tests
	$(PYTEST) tests/ui $(ARGS)

test-e2e: ## Track D: end-to-end user flows through the Flask test client
	$(PYTEST) tests/e2e $(ARGS)

test-slow: ## Slow tests only (large files); run before each milestone gate
	$(PYTEST) -m slow $(ARGS)

test-all: ## Every test, including slow ones
	$(PYTEST) $(ARGS)

build: ## Build the one-file executable into dist/
	uv run pyinstaller --noconfirm --clean $(SPEC)

smoke: ## Launch the built executable headless and check it answers on 127.0.0.1
	uv run python packaging/smoke_test.py

clean: ## Remove build output and caches
	rm -rf build dist .pytest_cache
