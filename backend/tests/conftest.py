import os
import socket

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret-123456")
os.environ.setdefault("ENV", "test")
os.environ.setdefault("BACKGROUND_WORKERS_ENABLED", "false")


def _postgres_up() -> bool:
    from sqlalchemy.engine import make_url

    from app.core.config import settings

    url = make_url(settings.database_url)
    try:
        with socket.create_connection((url.host or "localhost", url.port or 5432), timeout=1):
            return True
    except OSError:
        return False


def pytest_collection_modifyitems(config, items):
    if not any("integration" in item.keywords for item in items):
        return
    if _postgres_up():
        return
    skip = pytest.mark.skip(reason="postgres not reachable; integration tests skipped")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
