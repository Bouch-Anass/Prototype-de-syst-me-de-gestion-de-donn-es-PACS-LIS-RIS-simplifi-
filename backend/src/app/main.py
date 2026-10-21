"""Routes T03 et transport HL7 local T05."""

from datetime import datetime, timezone
import hmac
import os
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.errors import ACCESS_DENIED, NOT_FOUND, ApiError
from app.db.models import (
    AppSession, Encounter, ImagingStudy, Patient, RadiologyExam, RadiologyOrder,
    UserEncounterAccess,
)
from app.db.session import make_session_factory, session_dependency
from app.modules.audit.service import record_event
from app.modules.auth.service import authenticate, current_actor, require_csrf
from app.modules.identity.service import accessible_encounters, resolve_patient
from app.integrations.hl7.service import (
    MAX_MESSAGE_BYTES, ProfileError, build_ack, message_header, process_message, record_rejection,
)
from app.integrations.orthanc.client import OrthancClient, OrthancError, OrthancUnavailable
from app.modules.imaging.service import get_availability
from app.modules.summary.service import build_summary
from app.modules.radiology.service import (
    RadiologyError, create_order, mark_performed, save_report_draft, validate_report,
)


CLINICAL_IDENTITY_ROLES = {"physician", "radiologist", "lab_technician"}


class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=1024)


class RadiologyOrderBody(BaseModel):
    encounter_id: UUID
    accession_number: str = Field(min_length=1, max_length=100)
    requested_procedure: str = Field(min_length=1, max_length=200)
    modality: str = Field(min_length=1, max_length=20)
    priority: Literal["routine", "urgent"] = "routine"


class ExamPerformedBody(BaseModel):
    status: Literal["performed"]
    performed_at: datetime


class ReportDraftBody(BaseModel):
    content: str = Field(min_length=1, max_length=10000)


class ReportValidationBody(BaseModel):
    validated_at: datetime


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _error(request: Request, status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={
        "code": code, "message": message, "correlation_id": request.state.correlation_id,
    })


class _OfflineOrthanc:
    def get_study(self, orthanc_id: str, timeout_ms: int):
        raise OrthancUnavailable("ORTHANC_UNAVAILABLE")


def create_app(settings: Settings | None = None, session_factory: sessionmaker[Session] | None = None,
               orthanc_client: OrthancClient | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    session_factory = session_factory or make_session_factory(settings.database_url)
    if orthanc_client is None:
        connection = (os.getenv("ORTHANC_BASE_URL"), os.getenv("ORTHANC_USERNAME"), os.getenv("ORTHANC_PASSWORD"))
        orthanc_client = OrthancClient(*connection) if all(connection) else _OfflineOrthanc()
    get_db = session_dependency(session_factory)
    app = FastAPI(title="Dossier synthétique PACS/LIS/RIS", debug=False)

    @app.middleware("http")
    async def correlation(request: Request, call_next):
        request.state.correlation_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = request.state.correlation_id
        return response

    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError):
        return _error(request, exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return _error(request, 422, "INVALID_INPUT", "Données d'entrée invalides.")

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        return _error(request, 503, "SERVICE_UNAVAILABLE", "Service métier indisponible.")

    @app.get("/health/ready")
    def ready(request: Request, db: Session = Depends(get_db)):
        revision = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
        if revision != "0002_domains":
            raise ApiError(503, "SERVICE_UNAVAILABLE", "Service métier indisponible.")
        db.execute(text("SELECT 1")).scalar_one()
        with db.begin_nested() as probe:
            record_event(db, actor_user_id=None, action="health.ready", resource_type="service",
                         resource_id=None, outcome="probe", correlation_id=request.state.correlation_id)
            db.flush()
            probe.rollback()
        return {"status": "ready"}

    @app.post("/internal/hl7/messages")
    async def receive_hl7(request: Request):
        secret = settings.hl7_service_secret
        if not secret:
            raise ApiError(503, "SERVICE_UNAVAILABLE", "Service HL7 indisponible.")
        authorization = request.headers.get("authorization", "")
        if not hmac.compare_digest(authorization, f"Bearer {secret}"):
            raise ApiError(401, "UNAUTHENTICATED", "Authentification requise.")
        if request.headers.get("content-type", "").lower() != "application/hl7-v2; charset=utf-8":
            raise ApiError(415, "UNSUPPORTED_MEDIA_TYPE", "Type de message non accepté.")
        try:
            if int(request.headers.get("content-length", "0")) > MAX_MESSAGE_BYTES:
                raise ApiError(413, "PAYLOAD_TOO_LARGE", "Message trop volumineux.")
        except ValueError as exc:
            raise ApiError(422, "INVALID_INPUT", "Données d'entrée invalides.") from exc
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > MAX_MESSAGE_BYTES:
                raise ApiError(413, "PAYLOAD_TOO_LARGE", "Message trop volumineux.")
        payload = bytes(raw)
        _, control_id, kind = message_header(payload)
        try:
            process_message(session_factory, payload, request.state.correlation_id)
        except ProfileError as exc:
            try:
                record_rejection(session_factory, payload, exc.code, request.state.correlation_id)
            except SQLAlchemyError:
                return Response(content=build_ack(control_id, kind, "AE", "SERVICE_UNAVAILABLE"),
                                status_code=503, media_type="application/hl7-v2")
            status = 409 if exc.code in {"MESSAGE_CONFLICT", "ORDER_CONFLICT"} else 422
            return Response(content=build_ack(control_id, kind, "AR", exc.code),
                            status_code=status, media_type="application/hl7-v2")
        except SQLAlchemyError:
            return Response(content=build_ack(control_id, kind, "AE", "SERVICE_UNAVAILABLE"),
                            status_code=503, media_type="application/hl7-v2")
        return Response(content=build_ack(control_id, kind, "AA"),
                        status_code=200, media_type="application/hl7-v2")

    @app.post("/api/v1/auth/login")
    def login(body: LoginBody, request: Request, response: Response, db: Session = Depends(get_db)):
        if request.headers.get("origin") != settings.app_origin:
            raise ApiError(*ACCESS_DENIED)
        token, csrf, actor = authenticate(db, body.username, body.password, request.state.correlation_id)
        response.set_cookie("app_session", token, httponly=True, secure=settings.cookie_secure,
                            samesite="lax", max_age=8 * 60 * 60, path="/")
        response.set_cookie("csrf_token", csrf, httponly=False, secure=settings.cookie_secure,
                            samesite="lax", max_age=8 * 60 * 60, path="/")
        return {"user_id": actor.user_id, "username": actor.username, "roles": sorted(actor.roles)}

    @app.post("/api/v1/auth/logout")
    def logout(request: Request, response: Response, db: Session = Depends(get_db)):
        actor = current_actor(db, request)
        require_csrf(request, actor, settings.app_origin)
        db.delete(actor.session)
        record_event(db, actor_user_id=actor.user_id, action="auth.logout", resource_type="session",
                     resource_id=None, outcome="allowed", correlation_id=request.state.correlation_id)
        db.commit()
        response.delete_cookie("app_session", path="/")
        response.delete_cookie("csrf_token", path="/")
        return {"status": "logged_out"}

    def authorize_patient(db: Session, request: Request, patient: Patient | None, actor_id: str, roles: frozenset[str], action: str) -> list[Encounter]:
        if patient is None:
            record_event(db, actor_user_id=actor_id, action=action, resource_type="patient",
                         resource_id=None, outcome="not_found", correlation_id=request.state.correlation_id)
            db.commit()
            raise ApiError(*NOT_FOUND)
        encounters = accessible_encounters(db, actor_id, patient.id)
        if not roles.intersection(CLINICAL_IDENTITY_ROLES) or not encounters:
            record_event(db, actor_user_id=actor_id, action=action, resource_type="patient",
                         resource_id=patient.id, outcome="denied", correlation_id=request.state.correlation_id)
            db.commit()
            raise ApiError(*ACCESS_DENIED)
        return encounters

    @app.get("/api/v1/patients")
    def find_patients(request: Request, identifier: str = Query(min_length=1, max_length=100),
                      identifier_domain: str = Query(min_length=1, max_length=100),
                      db: Session = Depends(get_db)):
        actor = current_actor(db, request)
        patient = resolve_patient(db, identifier_domain, identifier)
        authorize_patient(db, request, patient, actor.user_id, actor.roles, "patient.search")
        record_event(db, actor_user_id=actor.user_id, action="patient.search", resource_type="patient",
                     resource_id=patient.id, outcome="allowed", correlation_id=request.state.correlation_id)
        db.commit()
        return {"patients": [{"id": patient.id, "external_id": patient.external_id,
                              "identifier_domain": patient.identifier_domain,
                              "display_name": patient.display_name, "is_synthetic": patient.is_synthetic}]}

    @app.get("/api/v1/patients/{patient_id}/encounters")
    def list_encounters(patient_id: UUID, request: Request, db: Session = Depends(get_db)):
        actor = current_actor(db, request)
        patient = db.get(Patient, str(patient_id))
        encounters = authorize_patient(db, request, patient, actor.user_id, actor.roles, "encounter.list")
        record_event(db, actor_user_id=actor.user_id, action="encounter.list", resource_type="patient",
                     resource_id=patient.id, outcome="allowed", correlation_id=request.state.correlation_id)
        db.commit()
        return {"encounters": [{"id": item.id, "patient_id": item.patient_id,
                                "external_id": item.external_id, "status": item.status,
                                "started_at": _timestamp(item.started_at),
                                "ended_at": _timestamp(item.ended_at) if item.ended_at else None}
                               for item in encounters]}

    @app.get("/api/v1/encounters/{encounter_id}/summary")
    def encounter_summary(encounter_id: UUID, request: Request, db: Session = Depends(get_db)):
        actor = current_actor(db, request)
        # Close the session transaction before the composition service starts its own transactions.
        db.commit()
        return build_summary(session_factory, orthanc_client, actor_user_id=actor.user_id,
                             encounter_id=str(encounter_id), correlation_id=request.state.correlation_id)

    def radiology_error(request: Request, actor_id: str, action: str,
                        resource_id: str | None, exc: RadiologyError):
        with session_factory.begin() as db:
            record_event(db, actor_user_id=actor_id, action=action, resource_type="radiology",
                         resource_id=resource_id, outcome="denied",
                         correlation_id=request.state.correlation_id)
        if exc.code == "ACCESS_DENIED":
            raise ApiError(*ACCESS_DENIED) from exc
        if exc.code in {"ENCOUNTER_UNKNOWN", "EXAM_UNKNOWN", "ORDER_UNKNOWN", "PATIENT_UNKNOWN"}:
            raise ApiError(*NOT_FOUND) from exc
        status = 409 if exc.code in {"ACCESSION_CONFLICT", "INVALID_TRANSITION"} else 422
        raise ApiError(status, exc.code, "Opération radiologique refusée.") from exc

    def radiology_actor(request: Request, db: Session):
        actor = current_actor(db, request)
        require_csrf(request, actor, settings.app_origin)
        db.commit()
        return actor

    @app.post("/api/v1/radiology-orders", status_code=201)
    def create_radiology_order(body: RadiologyOrderBody, request: Request, db: Session = Depends(get_db)):
        actor = radiology_actor(request, db)
        try:
            return create_order(session_factory, actor_user_id=actor.user_id,
                                encounter_id=str(body.encounter_id), accession_number=body.accession_number,
                                requested_procedure=body.requested_procedure, modality=body.modality,
                                priority=body.priority, correlation_id=request.state.correlation_id)
        except RadiologyError as exc:
            radiology_error(request, actor.user_id, "radiology.order.create", str(body.encounter_id), exc)

    @app.patch("/api/v1/radiology-exams/{exam_id}")
    def perform_radiology_exam(exam_id: UUID, body: ExamPerformedBody, request: Request,
                               db: Session = Depends(get_db)):
        actor = radiology_actor(request, db)
        try:
            mark_performed(session_factory, actor_user_id=actor.user_id, exam_id=str(exam_id),
                           performed_at=body.performed_at, correlation_id=request.state.correlation_id)
            return {"exam_id": str(exam_id), "status": "performed"}
        except RadiologyError as exc:
            radiology_error(request, actor.user_id, "radiology.exam.perform", str(exam_id), exc)

    @app.put("/api/v1/radiology-exams/{exam_id}/report")
    def draft_radiology_report(exam_id: UUID, body: ReportDraftBody, request: Request,
                               db: Session = Depends(get_db)):
        actor = radiology_actor(request, db)
        try:
            report_id = save_report_draft(session_factory, actor_user_id=actor.user_id,
                                          exam_id=str(exam_id), content=body.content,
                                          correlation_id=request.state.correlation_id)
            return {"report_id": report_id, "status": "draft"}
        except RadiologyError as exc:
            radiology_error(request, actor.user_id, "radiology.report.draft", str(exam_id), exc)

    @app.post("/api/v1/radiology-exams/{exam_id}/report/validate")
    def finalize_radiology_report(exam_id: UUID, body: ReportValidationBody, request: Request,
                                  db: Session = Depends(get_db)):
        actor = radiology_actor(request, db)
        try:
            report_id = validate_report(session_factory, actor_user_id=actor.user_id,
                                        exam_id=str(exam_id), validated_at=body.validated_at,
                                        correlation_id=request.state.correlation_id)
            return {"report_id": report_id, "status": "final"}
        except RadiologyError as exc:
            radiology_error(request, actor.user_id, "radiology.report.validate", str(exam_id), exc)

    def authorized_study(study_id: UUID, request: Request, db: Session, action: str):
        actor = current_actor(db, request)
        study = db.get(ImagingStudy, str(study_id))
        exam = db.get(RadiologyExam, study.exam_id) if study else None
        order = db.get(RadiologyOrder, exam.order_id) if exam else None
        if study is None or order is None:
            record_event(db, actor_user_id=actor.user_id, action=action, resource_type="imaging_study",
                         resource_id=None, outcome="not_found", correlation_id=request.state.correlation_id)
            db.commit()
            raise ApiError(*NOT_FOUND)
        grant = db.get(UserEncounterAccess, (actor.user_id, order.encounter_id))
        if not actor.roles.intersection({"physician", "radiologist"}) or grant is None:
            record_event(db, actor_user_id=actor.user_id, action=action, resource_type="imaging_study",
                         resource_id=study.id, outcome="denied", correlation_id=request.state.correlation_id)
            db.commit()
            raise ApiError(*ACCESS_DENIED)
        record_event(db, actor_user_id=actor.user_id, action=action, resource_type="imaging_study",
                     resource_id=study.id, outcome="allowed", correlation_id=request.state.correlation_id)
        result = (study.id, study.exam_id, study.orthanc_study_id)
        db.commit()
        return result

    @app.get("/api/v1/imaging-studies/{study_id}")
    def imaging_metadata(study_id: UUID, request: Request, db: Session = Depends(get_db)):
        authorized_study(study_id, request, db, "imaging.metadata")
        study = db.get(ImagingStudy, str(study_id))
        if study is None:
            raise ApiError(*NOT_FOUND)
        return {"id": study.id, "exam_id": study.exam_id,
                "study_instance_uid": study.study_instance_uid,
                "series_count": study.series_count, "instance_count": study.instance_count,
                "availability_status": study.availability_status,
                "last_synced_at": _timestamp(study.last_synced_at) if study.last_synced_at else None}

    @app.get("/api/v1/imaging-studies/{study_id}/viewer-link")
    def viewer_link(study_id: UUID, request: Request, db: Session = Depends(get_db)):
        _, exam_id, _ = authorized_study(study_id, request, db, "imaging.viewer_link")
        state = get_availability(session_factory, orthanc_client, exam_id=exam_id,
                                 correlation_id=request.state.correlation_id)
        if state["availability_status"] != "available":
            raise ApiError(503, "IMAGING_UNAVAILABLE", "Imagerie temporairement indisponible.")
        return {"url": f"/api/v1/imaging-studies/{study_id}/preview"}

    @app.get("/api/v1/imaging-studies/{study_id}/preview")
    def imaging_preview(study_id: UUID, request: Request, db: Session = Depends(get_db)):
        _, exam_id, orthanc_id = authorized_study(study_id, request, db, "imaging.preview")
        state = get_availability(session_factory, orthanc_client, exam_id=exam_id,
                                 correlation_id=request.state.correlation_id)
        if state["availability_status"] != "available" or not orthanc_id:
            raise ApiError(503, "IMAGING_UNAVAILABLE", "Imagerie temporairement indisponible.")
        try:
            image = orthanc_client.get_preview(orthanc_id, 500)
        except OrthancError as exc:
            raise ApiError(503, "IMAGING_UNAVAILABLE", "Imagerie temporairement indisponible.") from exc
        return Response(content=image, media_type="image/png",
                        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})

    return app


app = create_app()
