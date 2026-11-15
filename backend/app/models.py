"""Imports every ORM model so Base.metadata is complete (used by Alembic and tests)."""

from app.modules.agents.models import Agent  # noqa: F401
from app.modules.audit.models import AuditLog  # noqa: F401
from app.modules.events.models import OutboxEvent, ProcessedEvent  # noqa: F401
from app.modules.identity.models import User  # noqa: F401
from app.modules.organizations.models import Organization  # noqa: F401
from app.modules.runtime.models import Execution  # noqa: F401
