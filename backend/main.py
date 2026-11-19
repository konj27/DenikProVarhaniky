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
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.get("/health", response_model=schemas.HealthResponse, tags=["system"])
def health_check(
    _current_user: schemas.UserResponse = Depends(auth.get_current_user),
) -> schemas.HealthResponse:
    return models.get_health()


@app.get("/api/logs", response_model=list[schemas.LogEntryResponse], tags=["logs"])
def list_logs(
    skip: int = 0,
    limit: int = 100,
    _current_user: schemas.UserResponse = Depends(auth.get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> list[schemas.LogEntryResponse]:
    return models.list_logs(db=db, skip=skip, limit=limit)


@app.get("/api/logs/{log_id}", response_model=schemas.LogEntryResponse, tags=["logs"])
def read_log(
    log_id: int,
    _current_user: schemas.UserResponse = Depends(auth.get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> schemas.LogEntryResponse:
    return models.read_log(db=db, log_id=log_id)


@app.post(
    "/api/logs",
    response_model=schemas.LogEntryResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["logs"],
)
def create_log(
    log_in: schemas.LogEntryCreate,
    _current_user: schemas.UserResponse = Depends(auth.get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> schemas.LogEntryResponse:
    return models.create_log(db=db, log_in=log_in)


@app.patch("/api/logs/{log_id}", response_model=schemas.LogEntryResponse, tags=["logs"])
def update_log(
    log_id: int,
    log_in: schemas.LogEntryUpdate,
    _current_user: schemas.UserResponse = Depends(auth.get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> schemas.LogEntryResponse:
    return models.update_log(db=db, log_id=log_id, log_in=log_in)


@app.delete("/api/logs/{log_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["logs"])
def delete_log(
    log_id: int,
    _current_user: schemas.UserResponse = Depends(auth.get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> None:
    return models.delete_log(db=db, log_id=log_id)
