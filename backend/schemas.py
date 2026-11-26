from datetime import datetime
from pydantic import BaseModel, Field


# --- Request Schemas (Parameters) ---

class LogEntryCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, examples=["Sunday Morning Service"])
    author: str = Field(..., min_length=1, max_length=100, examples=["Jan Novak"])
    notes: str | None = Field(default=None, examples=["Played Prelude in C Major"])
    date: str | None = Field(default=None, examples=["2026-11-19T09:30:00"])
    parish_id: int = Field(..., ge=1, examples=[1])


class LogEntryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    author: str | None = Field(default=None, min_length=1, max_length=100)
    notes: str | None = None


class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, examples=["jan.novak"])
    password: str = Field(..., min_length=6, max_length=128)
    home_parish_id: int = Field(..., ge=1, examples=[1])
    master_password: str = Field(..., min_length=1)


class UserLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


class AccessRequestCreate(BaseModel):
    parish_id: int = Field(..., ge=1, examples=[2])


class UserParishGrantRequest(BaseModel):
    user_id: int = Field(..., ge=1)
    parish_id: int = Field(..., ge=1)


class DeniedRequestCreate(BaseModel):
    user_id: int = Field(..., ge=1)
    parish_id: int = Field(..., ge=1)
    reason: str | None = Field(default=None, max_length=500)
    requested_at: str | None = Field(default=None)


# --- Response Models ---

class HealthResponse(BaseModel):
    status: str


class ParishResponse(BaseModel):
    id: int
    name: str


class UserParishResponse(BaseModel):
    id: int
    name: str
    is_home: bool = False


class UserResponse(BaseModel):
    id: int
    username: str
    farnost: str | None = None
    is_admin: bool = False
    created_at: datetime


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class LogEntryResponse(BaseModel):
    id: int
    title: str
    author: str
    notes: str | None = None
    parish_id: int | None = None
    created_by_user_id: int | None = None
    created_at: datetime


class AccessRequestResponse(BaseModel):
    id: int
    user_id: int
    username: str
    parish_id: int
    parish_name: str
    created_at: datetime


class UserParishGrantResponse(BaseModel):
    user_id: int
    parish_id: int
    is_home: bool = False


class DeniedRequestResponse(BaseModel):
    id: int
    user_id: int
    parish_id: int
    reason: str | None = None
    denied_by: int | None = None
    requested_at: str | None = None
    denied_at: datetime
