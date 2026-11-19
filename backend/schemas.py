from datetime import datetime
from pydantic import BaseModel, Field


# --- Request Schemas (Parameters) ---

class LogEntryCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, examples=["Sunday Morning Service"])
    author: str = Field(..., min_length=1, max_length=100, examples=["Jan Novak"])
    notes: str | None = Field(default=None, examples=["Played Prelude in C Major"])
    date: str | None = Field(default=None, examples=["2026-11-19T09:30:00"])


class LogEntryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    author: str | None = Field(default=None, min_length=1, max_length=100)
    notes: str | None = None


class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, examples=["jan.novak"])
    password: str = Field(..., min_length=6, max_length=128)
    farnost: str | None = Field(default=None, max_length=100, examples=["Brno-střed"])
    master_password: str = Field(..., min_length=1)


class UserLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


# --- Response Models ---

class HealthResponse(BaseModel):
    status: str


class UserResponse(BaseModel):
    id: int
    username: str
    farnost: str | None = None
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
    created_at: datetime
