"""Tables communes et domaines métier du premier scénario synthétique."""

from datetime import datetime, timezone
from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Patient(Base):
    __tablename__ = "patient"
    __table_args__ = (UniqueConstraint("identifier_domain", "external_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    identifier_domain: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Encounter(Base):
    __tablename__ = "encounter"
    __table_args__ = (
        UniqueConstraint("patient_id", "external_id"),
        CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="ck_encounter_time"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    patient: Mapped[Patient] = relationship()


class AppUser(Base):
    __tablename__ = "app_user"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Role(Base):
    __tablename__ = "role"

    name: Mapped[str] = mapped_column(String(40), primary_key=True)


class UserRole(Base):
    __tablename__ = "user_role"

    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), primary_key=True)
    role_name: Mapped[str] = mapped_column(ForeignKey("role.name"), primary_key=True)


class UserEncounterAccess(Base):
    __tablename__ = "user_encounter_access"

    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), primary_key=True)
    encounter_id: Mapped[str] = mapped_column(ForeignKey("encounter.id"), primary_key=True)


class AppSession(Base):
    __tablename__ = "app_session"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), nullable=False, index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_event"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("app_user.id"))
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(36))
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class InboundMessage(Base):
    __tablename__ = "inbound_message"
    __table_args__ = (UniqueConstraint("source_system", "external_message_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_system: Mapped[str] = mapped_column(String(100), nullable=False)
    external_message_id: Mapped[str] = mapped_column(String(100), nullable=False)
    message_type: Mapped[str] = mapped_column(String(30), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    processing_status: Mapped[str] = mapped_column(String(30), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(50))


class LabOrder(Base):
    __tablename__ = "lab_order"
    __table_args__ = (UniqueConstraint("source_system", "placer_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    encounter_id: Mapped[str] = mapped_column(ForeignKey("encounter.id"), nullable=False, index=True)
    source_system: Mapped[str] = mapped_column(String(100), nullable=False)
    placer_number: Mapped[str] = mapped_column(String(100), nullable=False)
    filler_number: Mapped[str] = mapped_column(String(100), nullable=False)
    panel_code: Mapped[str] = mapped_column(String(60), nullable=False)
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)


class LabReport(Base):
    __tablename__ = "lab_report"
    __table_args__ = (UniqueConstraint("lab_order_id", "version"), CheckConstraint("version > 0", name="ck_lab_version"))

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    lab_order_id: Mapped[str] = mapped_column(ForeignKey("lab_order.id"), nullable=False, index=True)
    inbound_message_id: Mapped[str | None] = mapped_column(ForeignKey("inbound_message.id"), unique=True)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class LabObservation(Base):
    __tablename__ = "lab_observation"
    __table_args__ = (
        CheckConstraint("data_status IN ('available', 'missing', 'invalid')", name="ck_lab_data_status"),
        CheckConstraint("(data_status = 'available' AND ((value_numeric IS NOT NULL AND value_text IS NULL) OR (value_numeric IS NULL AND value_text IS NOT NULL))) OR (data_status != 'available' AND value_numeric IS NULL AND value_text IS NULL)", name="ck_lab_value"),
        UniqueConstraint("lab_report_id", "coding_system", "code"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    lab_report_id: Mapped[str] = mapped_column(ForeignKey("lab_report.id"), nullable=False, index=True)
    coding_system: Mapped[str] = mapped_column(String(40), nullable=False)
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    display: Mapped[str] = mapped_column(String(120), nullable=False)
    value_numeric: Mapped[float | None] = mapped_column(Float)
    value_text: Mapped[str | None] = mapped_column(String(200))
    unit: Mapped[str | None] = mapped_column(String(40))
    data_status: Mapped[str] = mapped_column(String(20), nullable=False)


class RadiologyOrder(Base):
    __tablename__ = "radiology_order"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    encounter_id: Mapped[str] = mapped_column(ForeignKey("encounter.id"), nullable=False, index=True)
    accession_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    requested_procedure: Mapped[str] = mapped_column(String(200), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)


class RadiologyExam(Base):
    __tablename__ = "radiology_exam"
    __table_args__ = (CheckConstraint("status != 'performed' OR performed_at IS NOT NULL", name="ck_exam_performed"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("radiology_order.id"), nullable=False, unique=True)
    modality: Mapped[str] = mapped_column(String(20), nullable=False)
    performed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), nullable=False)


class RadiologyReport(Base):
    __tablename__ = "radiology_report"
    __table_args__ = (CheckConstraint("status NOT IN ('final', 'amended') OR validated_at IS NOT NULL", name="ck_report_validated"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    exam_id: Mapped[str] = mapped_column(ForeignKey("radiology_exam.id"), nullable=False, unique=True)
    author_user_id: Mapped[str | None] = mapped_column(ForeignKey("app_user.id"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ImagingStudy(Base):
    __tablename__ = "imaging_study"
    __table_args__ = (
        CheckConstraint("series_count >= 0 AND instance_count >= 0", name="ck_study_counts"),
        CheckConstraint("availability_status IN ('available', 'incomplete', 'unavailable')", name="ck_study_availability"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    exam_id: Mapped[str] = mapped_column(ForeignKey("radiology_exam.id"), nullable=False, unique=True)
    study_instance_uid: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    orthanc_study_id: Mapped[str | None] = mapped_column(String(100))
    modality: Mapped[str] = mapped_column(String(20), nullable=False)
    series_count: Mapped[int] = mapped_column(Integer, nullable=False)
    instance_count: Mapped[int] = mapped_column(Integer, nullable=False)
    availability_status: Mapped[str] = mapped_column(String(20), nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
