.PHONY: setup check lint test build audit package-deb package-rpm clean

setup:
	uv sync --locked --extra gui

check: lint test
	uv run --locked python scripts/check-release.py
	uv lock --check

lint:
	uv run --locked ruff check src scripts tests
	uv run --locked ruff format --check scripts/*.py tests
	actionlint
	shellcheck install.sh bin/*.sh scripts/*.sh packaging/*.sh packaging/deb/*.sh
	uv run --locked zizmor --offline .github/workflows

test:
	uv run --locked pytest

build:
	uv run --locked python -m build --no-isolation
	uv run --locked twine check dist/*.whl dist/*.tar.gz

audit:
	uv run --locked bash scripts/security-audit.sh

package-deb:
	docker build --platform linux/amd64 -f packaging/containers/debian.Dockerfile --output type=local,dest=dist/packages/ubuntu24.04 .

package-rpm:
	docker build --platform linux/amd64 -f packaging/containers/fedora.Dockerfile --output type=local,dest=dist/packages/fedora .

clean:
	rm -rf build dist .pytest_cache .ruff_cache
