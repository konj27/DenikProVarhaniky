import ipaddress
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import auth
from .database import BASE_DIR, init_db
from .routes import router

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


app.include_router(router)
