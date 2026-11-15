"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-15
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )

    op.create_table(
        "users",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "organization_id",
            UUID,
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
        _ts("last_login_at", nullable=True),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.CheckConstraint("role IN ('owner','admin','operator','viewer')", name="ck_users_role"),
    )
    op.create_index("ix_users_organization_id", "users", ["organization_id"])

    op.create_table(
        "agents",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "organization_id",
            UUID,
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("role", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("system_instructions", sa.Text, nullable=False),
        sa.Column("objectives", JSONB, nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("autonomy_level", sa.Integer, nullable=False),
        sa.Column(
            "supervisor_agent_id",
            UUID,
            sa.ForeignKey("agents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("execution_mode", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("created_by", UUID, nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.UniqueConstraint("organization_id", "name", name="uq_agents_org_name"),
        sa.CheckConstraint("autonomy_level BETWEEN 1 AND 4", name="ck_agents_autonomy"),
        sa.CheckConstraint("execution_mode IN ('simulated','live')", name="ck_agents_exec_mode"),
        sa.CheckConstraint(
            "status IN ('draft','active','paused','disabled','archived','terminated')",
            name="ck_agents_status",
        ),
    )
    op.create_index("ix_agents_organization_id", "agents", ["organization_id"])
    op.create_index("ix_agents_supervisor_agent_id", "agents", ["supervisor_agent_id"])
    op.create_index("ix_agents_org_status", "agents", ["organization_id", "status"])

    op.create_table(
        "executions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "organization_id",
            UUID,
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id", UUID, sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("requested_by", UUID, nullable=True),
        sa.Column("input_prompt", sa.Text, nullable=False),
        sa.Column("output", sa.Text, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("agent_version", sa.Integer, nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=True),
        sa.Column("output_tokens", sa.Integer, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("cost_usd", sa.Float, nullable=True),
        sa.Column("trace_id", sa.String(64), nullable=False),
        _ts("created_at"),
        _ts("started_at", nullable=True),
        _ts("finished_at", nullable=True),
        sa.CheckConstraint(
            "status IN ('queued','running','succeeded','failed')", name="ck_executions_status"
        ),
        sa.CheckConstraint("mode IN ('simulated','live')", name="ck_executions_mode"),
    )
    op.create_index("ix_executions_organization_id", "executions", ["organization_id"])
    op.create_index("ix_executions_agent_id", "executions", ["agent_id"])
    op.create_index("ix_executions_org_created", "executions", ["organization_id", "created_at"])

    op.create_table(
        "outbox_events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("type", sa.String(60), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("organization_id", UUID, nullable=False),
        _ts("occurred_at"),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("trace_id", sa.String(64), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        _ts("published_at", nullable=True),
    )
    op.create_index("ix_outbox_events_organization_id", "outbox_events", ["organization_id"])
    op.create_index(
        "ix_outbox_unpublished",
        "outbox_events",
        ["occurred_at"],
        postgresql_where=sa.text("published_at IS NULL"),
    )

    op.create_table(
        "processed_events",
        sa.Column("consumer", sa.String(80), primary_key=True),
        sa.Column("event_id", UUID, primary_key=True),
        _ts("processed_at"),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("actor_user_id", UUID, nullable=True),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("resource_type", sa.String(60), nullable=False),
        sa.Column("resource_id", sa.String(64), nullable=True),
        sa.Column("before", JSONB, nullable=True),
        sa.Column("after", JSONB, nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(64), nullable=True),
        _ts("created_at"),
    )
    op.create_index("ix_audit_logs_organization_id", "audit_logs", ["organization_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_org_created", "audit_logs", ["organization_id", "created_at"])

    # Append-only enforcement for the audit log.
    op.execute(
        """
        CREATE FUNCTION audit_logs_immutable() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_logs_no_update_delete
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION audit_logs_immutable()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_logs_no_update_delete ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS audit_logs_immutable()")
    for table in (
        "audit_logs",
        "processed_events",
        "outbox_events",
        "executions",
        "agents",
        "users",
        "organizations",
    ):
        op.drop_table(table)
