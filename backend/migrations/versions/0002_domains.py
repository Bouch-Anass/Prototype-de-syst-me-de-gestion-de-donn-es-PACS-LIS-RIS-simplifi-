"""Laboratory, radiology, imaging and inbound-message tables.

Revision ID: 0002_domains
Revises: 0001_t03
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_domains"
down_revision = "0001_t03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inbound_message",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_system", sa.String(100), nullable=False),
        sa.Column("external_message_id", sa.String(100), nullable=False),
        sa.Column("message_type", sa.String(30), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processing_status", sa.String(30), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("error_code", sa.String(50)),
        sa.UniqueConstraint("source_system", "external_message_id"),
    )
    op.create_table(
        "lab_order",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("encounter_id", sa.String(36), sa.ForeignKey("encounter.id"), nullable=False),
        sa.Column("source_system", sa.String(100), nullable=False),
        sa.Column("placer_number", sa.String(100), nullable=False),
        sa.Column("filler_number", sa.String(100), nullable=False),
        sa.Column("panel_code", sa.String(60), nullable=False),
        sa.Column("ordered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.UniqueConstraint("source_system", "placer_number"),
    )
    op.create_index("ix_lab_order_encounter_id", "lab_order", ["encounter_id"])
    op.create_table(
        "lab_report",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("lab_order_id", sa.String(36), sa.ForeignKey("lab_order.id"), nullable=False),
        sa.Column("inbound_message_id", sa.String(36), sa.ForeignKey("inbound_message.id"), unique=True),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("lab_order_id", "version"),
        sa.CheckConstraint("version > 0", name="ck_lab_version"),
    )
    op.create_index("ix_lab_report_lab_order_id", "lab_report", ["lab_order_id"])
    op.create_table(
        "lab_observation",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("lab_report_id", sa.String(36), sa.ForeignKey("lab_report.id"), nullable=False),
        sa.Column("coding_system", sa.String(40), nullable=False),
        sa.Column("code", sa.String(60), nullable=False),
        sa.Column("display", sa.String(120), nullable=False),
        sa.Column("value_numeric", sa.Float()),
        sa.Column("value_text", sa.String(200)),
        sa.Column("unit", sa.String(40)),
        sa.Column("data_status", sa.String(20), nullable=False),
        sa.UniqueConstraint("lab_report_id", "coding_system", "code"),
        sa.CheckConstraint("data_status IN ('available', 'missing', 'invalid')", name="ck_lab_data_status"),
        sa.CheckConstraint("(data_status = 'available' AND ((value_numeric IS NOT NULL AND value_text IS NULL) OR (value_numeric IS NULL AND value_text IS NOT NULL))) OR (data_status != 'available' AND value_numeric IS NULL AND value_text IS NULL)", name="ck_lab_value"),
    )
    op.create_index("ix_lab_observation_lab_report_id", "lab_observation", ["lab_report_id"])
    op.create_table(
        "radiology_order",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("encounter_id", sa.String(36), sa.ForeignKey("encounter.id"), nullable=False),
        sa.Column("accession_number", sa.String(100), nullable=False, unique=True),
        sa.Column("requested_procedure", sa.String(200), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
    )
    op.create_index("ix_radiology_order_encounter_id", "radiology_order", ["encounter_id"])
    op.create_table(
        "radiology_exam",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("radiology_order.id"), nullable=False, unique=True),
        sa.Column("modality", sa.String(20), nullable=False),
        sa.Column("performed_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(30), nullable=False),
        sa.CheckConstraint("status != 'performed' OR performed_at IS NOT NULL", name="ck_exam_performed"),
    )
    op.create_table(
        "radiology_report",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("exam_id", sa.String(36), sa.ForeignKey("radiology_exam.id"), nullable=False, unique=True),
        sa.Column("author_user_id", sa.String(36), sa.ForeignKey("app_user.id")),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status NOT IN ('final', 'amended') OR validated_at IS NOT NULL", name="ck_report_validated"),
    )
    op.create_table(
        "imaging_study",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("exam_id", sa.String(36), sa.ForeignKey("radiology_exam.id"), nullable=False, unique=True),
        sa.Column("study_instance_uid", sa.String(100), nullable=False, unique=True),
        sa.Column("orthanc_study_id", sa.String(100)),
        sa.Column("modality", sa.String(20), nullable=False),
        sa.Column("series_count", sa.Integer(), nullable=False),
        sa.Column("instance_count", sa.Integer(), nullable=False),
        sa.Column("availability_status", sa.String(20), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("series_count >= 0 AND instance_count >= 0", name="ck_study_counts"),
        sa.CheckConstraint("availability_status IN ('available', 'incomplete', 'unavailable')", name="ck_study_availability"),
    )


def downgrade() -> None:
    op.drop_table("imaging_study")
    op.drop_table("radiology_report")
    op.drop_table("radiology_exam")
    op.drop_index("ix_radiology_order_encounter_id", table_name="radiology_order")
    op.drop_table("radiology_order")
    op.drop_index("ix_lab_observation_lab_report_id", table_name="lab_observation")
    op.drop_table("lab_observation")
    op.drop_index("ix_lab_report_lab_order_id", table_name="lab_report")
    op.drop_table("lab_report")
    op.drop_index("ix_lab_order_encounter_id", table_name="lab_order")
    op.drop_table("lab_order")
    op.drop_table("inbound_message")
