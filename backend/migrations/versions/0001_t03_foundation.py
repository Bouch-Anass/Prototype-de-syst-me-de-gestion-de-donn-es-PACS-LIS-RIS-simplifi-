"""T03 identity, access, sessions and audit.

Revision ID: 0001_t03
Revises:
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_t03"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patient",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("identifier_domain", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("identifier_domain", "external_id"),
    )
    op.create_table(
        "encounter",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("patient.id"), nullable=False),
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("patient_id", "external_id"),
        sa.CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="ck_encounter_time"),
    )
    op.create_index("ix_encounter_patient_id", "encounter", ["patient_id"])
    op.create_table(
        "app_user",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
    )
    op.create_table("role", sa.Column("name", sa.String(40), primary_key=True))
    role_table = sa.table("role", sa.column("name", sa.String(40)))
    op.bulk_insert(role_table, [{"name": role} for role in ("physician", "radiologist", "lab_technician", "admin")])
    op.create_table(
        "user_role",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("app_user.id"), primary_key=True),
        sa.Column("role_name", sa.String(40), sa.ForeignKey("role.name"), primary_key=True),
    )
    op.create_table(
        "user_encounter_access",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("app_user.id"), primary_key=True),
        sa.Column("encounter_id", sa.String(36), sa.ForeignKey("encounter.id"), primary_key=True),
    )
    op.create_table(
        "app_session",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_app_session_user_id", "app_session", ["user_id"])
    op.create_table(
        "audit_event",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("app_user.id")),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("resource_type", sa.String(40), nullable=False),
        sa.Column("resource_id", sa.String(36)),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("correlation_id", sa.String(36), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_event")
    op.drop_index("ix_app_session_user_id", table_name="app_session")
    op.drop_table("app_session")
    op.drop_table("user_encounter_access")
    op.drop_table("user_role")
    op.drop_table("role")
    op.drop_table("app_user")
    op.drop_index("ix_encounter_patient_id", table_name="encounter")
    op.drop_table("encounter")
    op.drop_table("patient")
