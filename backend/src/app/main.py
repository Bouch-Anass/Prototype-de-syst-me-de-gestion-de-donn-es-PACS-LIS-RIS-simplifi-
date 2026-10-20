"""Premières routes T03 : identité, contexte, session et audit."""

from datetime import datetime, timezone
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


def create_app(settings: Settings | None = None, session_factory: sessionmaker[Session] | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    session_factory = session_factory or make_session_factory(settings.database_url)
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

    return app


app = create_app()
