import ipaddress
import os
import sqlite3
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials

from . import auth, models, schemas
from .database import BASE_DIR, get_db, init_db

load_dotenv(BASE_DIR / ".env", override=False)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _parse_allowed_networks(raw: str) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network] | None:
    """Parse comma-separated IPs/CIDRs. Returns None when wildcard '*' allows all IPs."""
    entries = [part.strip() for part in raw.split(",") if part.strip()]
    if "*" in entries:
        return None
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for entry in entries:
        networks.append(ipaddress.ip_network(entry, strict=False))
    return networks


def _is_ip_allowed(
    client_ip: str,
    allowed_networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] | None,
) -> bool:
    if allowed_networks is None:
        return True
    try:
        addr = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    return any(addr.version == net.version and addr in net for net in allowed_networks)


ENABLE_API_DOCS = _env_bool("ENABLE_API_DOCS", default=False)
ALLOWED_BACKEND_NETWORKS = _parse_allowed_networks(
    os.getenv("BACKEND_ALLOWED_IPS", "127.0.0.1,::1")
)
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:8501,http://127.0.0.1:8501",
    ).split(",")
    if origin.strip()
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Varhanici Log Page API",
    description="FastAPI backend using standard sqlite3, schemas, and models.",
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs" if ENABLE_API_DOCS else None,
    redoc_url="/redoc" if ENABLE_API_DOCS else None,
    openapi_url="/openapi.json" if ENABLE_API_DOCS else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials="*" not in CORS_ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def enforce_backend_ip_allowlist(request: Request, call_next):
    client_ip = auth.get_client_ip(request)
    if not _is_ip_allowed(client_ip, ALLOWED_BACKEND_NETWORKS):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Přístup k backendu není z této IP adresy povolen."},
        )
    return await call_next(request)


# --- Auth ---

@app.post(
    "/api/auth/register",
    response_model=schemas.AuthTokenResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["auth"],
)
def register(
    user_in: schemas.UserRegisterRequest,
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
) -> schemas.AuthTokenResponse:
    return models.register_user(
        db=db,
        user_in=user_in,
        client_ip=auth.get_client_ip(request),
    )


@app.post(
    "/api/auth/login",
    response_model=schemas.AuthTokenResponse,
    tags=["auth"],
)
def login(
    credentials: schemas.UserLoginRequest,
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
) -> schemas.AuthTokenResponse:
    return models.login_user(
        db=db,
        credentials=credentials,
        client_ip=auth.get_client_ip(request),
    )


@app.post(
    "/api/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["auth"],
)
def logout(
    _current_user: schemas.UserResponse = Depends(auth.get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(auth.bearer_scheme),
    db: sqlite3.Connection = Depends(get_db),
) -> None:
    if credentials and credentials.credentials:
        models.logout_user(db=db, token=credentials.credentials)
    return None


@app.get("/api/auth/me", response_model=schemas.UserResponse, tags=["auth"])
def read_current_user(
    current_user: schemas.UserResponse = Depends(auth.get_current_user),
) -> schemas.UserResponse:
    return current_user


# --- System ---

@app.get("/health", response_model=schemas.HealthResponse, tags=["system"])
def health_check(
    _current_user: schemas.UserResponse = Depends(auth.get_current_user),
) -> schemas.HealthResponse:
    return models.get_health()


# --- Parishes ---

@app.get("/api/parishes", response_model=list[schemas.ParishResponse], tags=["parishes"])
def list_parishes(
    db: sqlite3.Connection = Depends(get_db),
) -> list[schemas.ParishResponse]:
    return models.list_all_parishes(db=db)


@app.get("/api/parishes/mine", response_model=list[schemas.UserParishResponse], tags=["parishes"])
def list_my_parishes(
    current_user: schemas.UserResponse = Depends(auth.get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> list[schemas.UserParishResponse]:
    return models.list_user_parishes(db=db, current_user=current_user)


# --- Access Requests ---

@app.post(
    "/api/access-requests",
    response_model=schemas.AccessRequestResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["access-requests"],
)
def create_access_request(
    req_in: schemas.AccessRequestCreate,
    current_user: schemas.UserResponse = Depends(auth.get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> schemas.AccessRequestResponse:
    return models.create_access_request(db=db, current_user=current_user, req_in=req_in)


@app.get(
    "/api/access-requests/mine",
    response_model=list[schemas.AccessRequestResponse],
    tags=["access-requests"],
)
def list_my_access_requests(
    current_user: schemas.UserResponse = Depends(auth.get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> list[schemas.AccessRequestResponse]:
    return models.list_my_access_requests(db=db, current_user=current_user)


# --- Admin ---

@app.get(
    "/api/admin/access-requests",
    response_model=list[schemas.AccessRequestResponse],
    tags=["admin"],
)
def admin_list_access_requests(
    _admin_user: schemas.UserResponse = Depends(auth.require_admin),
    db: sqlite3.Connection = Depends(get_db),
) -> list[schemas.AccessRequestResponse]:
    return models.list_all_access_requests(db=db)


@app.delete(
    "/api/admin/access-requests/{request_id}",
    response_model=schemas.AccessRequestResponse,
    tags=["admin"],
)
def admin_delete_access_request(
    request_id: int,
    _admin_user: schemas.UserResponse = Depends(auth.require_admin),
    db: sqlite3.Connection = Depends(get_db),
) -> schemas.AccessRequestResponse:
    return models.delete_access_request(db=db, request_id=request_id)


@app.post(
    "/api/admin/user-parishes",
    response_model=schemas.UserParishGrantResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["admin"],
)
def admin_grant_user_parish(
    grant_in: schemas.UserParishGrantRequest,
    _admin_user: schemas.UserResponse = Depends(auth.require_admin),
    db: sqlite3.Connection = Depends(get_db),
) -> schemas.UserParishGrantResponse:
    return models.grant_user_parish(db=db, grant_in=grant_in)


@app.post(
    "/api/admin/denied-requests",
    response_model=schemas.DeniedRequestResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["admin"],
)
def admin_create_denied_request(
    denied_in: schemas.DeniedRequestCreate,
    admin_user: schemas.UserResponse = Depends(auth.require_admin),
    db: sqlite3.Connection = Depends(get_db),
) -> schemas.DeniedRequestResponse:
    return models.create_denied_request(db=db, admin_user=admin_user, denied_in=denied_in)


# --- Logs ---

@app.get("/api/logs", response_model=list[schemas.LogEntryResponse], tags=["logs"])
def list_logs(
    parish_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
    current_user: schemas.UserResponse = Depends(auth.get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> list[schemas.LogEntryResponse]:
    return models.list_logs(
        db=db,
        current_user=current_user,
        parish_id=parish_id,
        skip=skip,
        limit=limit,
    )


@app.get("/api/logs/{log_id}", response_model=schemas.LogEntryResponse, tags=["logs"])
def read_log(
    log_id: int,
    current_user: schemas.UserResponse = Depends(auth.get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> schemas.LogEntryResponse:
    return models.read_log(db=db, log_id=log_id, current_user=current_user)


@app.post(
    "/api/logs",
    response_model=schemas.LogEntryResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["logs"],
)
def create_log(
    log_in: schemas.LogEntryCreate,
    current_user: schemas.UserResponse = Depends(auth.get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> schemas.LogEntryResponse:
    return models.create_log(db=db, log_in=log_in, current_user=current_user)


@app.patch("/api/logs/{log_id}", response_model=schemas.LogEntryResponse, tags=["logs"])
def update_log(
    log_id: int,
    log_in: schemas.LogEntryUpdate,
    current_user: schemas.UserResponse = Depends(auth.get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> schemas.LogEntryResponse:
    return models.update_log(db=db, log_id=log_id, log_in=log_in, current_user=current_user)


@app.delete("/api/logs/{log_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["logs"])
def delete_log(
    log_id: int,
    current_user: schemas.UserResponse = Depends(auth.get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> None:
    return models.delete_log(db=db, log_id=log_id, current_user=current_user)
