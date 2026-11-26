import sqlite3
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials

from . import auth, models, schemas
from .database import get_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Varhanici Log Page API",
    description="FastAPI backend using standard sqlite3, schemas, and models.",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Auth ---

@app.post(
    "/api/auth/register",
    response_model=schemas.AuthTokenResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["auth"],
)
def register(
    user_in: schemas.UserRegisterRequest,
    db: sqlite3.Connection = Depends(get_db),
) -> schemas.AuthTokenResponse:
    return models.register_user(db=db, user_in=user_in)


@app.post(
    "/api/auth/login",
    response_model=schemas.AuthTokenResponse,
    tags=["auth"],
)
def login(
    credentials: schemas.UserLoginRequest,
    db: sqlite3.Connection = Depends(get_db),
) -> schemas.AuthTokenResponse:
    return models.login_user(db=db, credentials=credentials)


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
