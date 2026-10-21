"""Routes T03 et transport HL7 local T05."""

from datetime import datetime, timezone
import hmac
import os
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.errors import ACCESS_DENIED, NOT_FOUND, ApiError
from app.db.models import AppSession, Encounter, Patient
from app.db.session import make_session_factory, session_dependency
from app.modules.audit.service import record_event
from app.modules.auth.service import authenticate, current_actor, require_csrf
from app.modules.identity.service import accessible_encounters, resolve_patient
from app.integrations.hl7.service import (
    MAX_MESSAGE_BYTES, ProfileError, build_ack, message_header, process_message, record_rejection,
)
from app.integrations.orthanc.client import OrthancClient, OrthancUnavailable
from app.modules.summary.service import build_summary



CLINICAL_IDENTITY_ROLES = {"physician", "radiologist", "lab_technician"}


class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=1024)


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

    return app


app = create_app()
