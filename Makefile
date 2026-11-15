.PHONY: up down logs migrate test lint test-local build-test-image

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

migrate:
	docker compose exec backend alembic upgrade head

build-test-image:
	docker build -t agentos-backend-test --build-arg INSTALL_DEV=true backend

# Unit tests only (no infrastructure needed), run inside a container with dev deps.
test: build-test-image
	docker run --rm agentos-backend-test pytest -p no:cacheprovider -m "not integration"

lint: build-test-image
	docker run --rm agentos-backend-test ruff check .

# Run tests on the host (needs Python 3.12 and `pip install -e "backend[dev]"`).
# Add `-m integration` once `make up` is running and migrations applied.
test-local:
	cd backend && pytest -m "not integration"
