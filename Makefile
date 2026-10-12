# Developer tasks for the Lutris source tree.
#
# Release, packaging and upload automation lives in packaging/Makefile and is
# run from the repository root (so debuild/git-buildpackage find ./debian) as:
#
#     make -f packaging/Makefile <target>
#
# Run `make help` to list the common developer targets.

PYTHON ?= python3
UV ?= uv
PYGOBJECT_STUBS_CONFIG = --config-settings-package pygobject-stubs:config=Gtk3,Gdk3,Soup2

.DEFAULT_GOAL := help
.PHONY: help test cover sync install-hooks dev style format check ruff_lint syntax-compat annotation-compat po-check mypy mypy-reset-baseline appimage sc styles checks

help:
	@echo "Common developer tasks:"
	@echo "  make dev            Create the development environment and install dependencies"
	@echo "  make sync           Sync Python dependencies from uv.lock"
	@echo "  make test           Run the unit test suite"
	@echo "  make cover          Run the test suite with a coverage report"
	@echo "  make check          Run every static-analysis check"
	@echo "  make style          Check code formatting (ruff format --check)"
	@echo "  make format         Auto-format code and sort imports"
	@echo "  make mypy           Run mypy against the baseline"
	@echo "  make appimage       Build the AppImage"
	@echo "  make install-hooks  Install the git pre-commit hook"
	@echo
	@echo "Release/packaging tasks: make -f packaging/Makefile help"

# ======
# Tests
# ======

test: sync
	rm tests/fixtures/pga.db -f
	$(UV) run --locked --no-sync nose2

cover: sync
	rm tests/fixtures/pga.db -f
	rm tests/coverage/ -rf
	$(UV) run --locked --no-sync nose2 --with-coverage --cover-package=lutris --cover-html --cover-html-dir=tests/coverage

# ==================
# Environment setup
# ==================

sync:
	$(UV) venv --python "$(PYTHON)" --system-site-packages
	$(UV) sync --locked --group dev $(PYGOBJECT_STUBS_CONFIG)

install-hooks:
	ln -sf -t .git/hooks/ ../../.hooks/pre-commit

dev: sync install-hooks

# ============
# Style checks
# ============

style: sync
	$(UV) run --locked --no-sync ruff format . --check

format: sync
	$(UV) run --locked --no-sync ruff check --select I --fix
	$(UV) run --locked --no-sync ruff format .

# ===============
# Static analysis
# ===============

check: sync ruff_lint mypy syntax-compat annotation-compat po-check

ruff_lint: sync
	$(UV) run --locked --no-sync ruff check .

syntax-compat:
	python3 -m compileall -q lutris/

annotation-compat:
	python3 utils/check_annotations.py

po-check:
	@for f in po/*.po; do msgfmt --check "$$f" -o /dev/null; done

mypy: sync
	$(UV) run --locked --no-sync mypy . --python-version 3.10 2>&1 | $(UV) run --locked --no-sync mypy-baseline filter

mypy-reset-baseline: sync  # Add new typing errors to mypy. Use sparingly.
	$(UV) run --locked --no-sync mypy . --python-version 3.10 2>&1 | $(UV) run --locked --no-sync mypy-baseline sync

# ==============================
# Packaging (developer-facing)
# ==============================

appimage:
	utils/appimage/build.sh

# =============
# Abbreviations
# =============

sc: style check
styles: style
checks: check
