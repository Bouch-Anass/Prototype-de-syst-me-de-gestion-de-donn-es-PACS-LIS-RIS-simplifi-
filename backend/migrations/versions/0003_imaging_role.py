"""Add the synthetic imaging technician role.

Revision ID: 0003_imaging_role
Revises: 0002_domains
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_imaging_role"
down_revision = "0002_domains"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.bulk_insert(sa.table("role", sa.column("name", sa.String(40))),
                   [{"name": "imaging_technician"}])


def downgrade() -> None:
    op.execute("DELETE FROM role WHERE name = 'imaging_technician'")
