.PHONY: dev test lint bench eval deploy teardown selfcheck

dev:
	docker compose up

test:
	python -m pytest vision/tests/ -v

lint:
	python -m ruff check vision/ || true
	python -m mypy vision/ || true

bench:
	python -m benchmarks.run --suite default --reps 10 --out results/

eval:
	python -m eval.run --suite default --agent mock --out reports/

selfcheck:
	python -m zoneshield.selfcheck

teardown:
	./scripts/teardown.sh

install:
	pip install opencv-python-headless numpy pydantic pydantic-settings pytest pytest-asyncio msgpack