import os
import time
from collections import defaultdict

from dotenv import load_dotenv
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import inspect, text

from auth import router as auth_router
from chat import router as chat_router
from connections import router as connections_router
from database import Base, engine, db_session
from history import router as history_router
from memory import router as memory_router
from models import User
from query import router as query_router
from queries import router as queries_router
from upload import router as upload_router
from security import get_password_hash

load_dotenv()

RATE_LIMIT_REQUESTS_PER_MINUTE = int(os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "120"))
_rate_limit_store: dict[str, list[float]] = defaultdict(list)

app = FastAPI(title="SQL Query AI", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",")],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(_: Request, __: SQLAlchemyError):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Database operation failed"},
    )


@app.get("/")
def read_root():
    return {"status": "running", "message": "SQL Query AI API"}


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
        request.client.host if request.client else "unknown"
    )
    now = time.time()
    window_start = now - 60
    timestamps = [stamp for stamp in _rate_limit_store[client_ip] if stamp >= window_start]
    if len(timestamps) >= RATE_LIMIT_REQUESTS_PER_MINUTE:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Rate limit exceeded"},
        )
    timestamps.append(now)
    _rate_limit_store[client_ip] = timestamps
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


app.include_router(auth_router)
app.include_router(query_router)
app.include_router(history_router)
app.include_router(memory_router)
app.include_router(chat_router)
app.include_router(connections_router)
app.include_router(queries_router)
app.include_router(upload_router)


def _seed_default_admin() -> None:
    admin_email = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@example.com").strip().lower()
    admin_password = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")
    admin_name = os.getenv("DEFAULT_ADMIN_NAME", "Administrator")
    with db_session() as db:
        admin = db.query(User).filter(User.email == admin_email).first()
        if admin is None:
            db.add(
                User(
                    full_name=admin_name,
                    email=admin_email,
                    password_hash=get_password_hash(admin_password),
                    role="admin",
                    is_verified=True,
                )
            )


def _ensure_sqlite_compatibility() -> None:
    if not str(engine.url).startswith("sqlite"):
        return
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    if "users" in existing_tables:
        columns = {column["name"] for column in inspector.get_columns("users")}
        with engine.begin() as conn:
            if "is_verified" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN is_verified BOOLEAN NOT NULL DEFAULT 0"))
            if "updated_at" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN updated_at DATETIME"))


Base.metadata.create_all(bind=engine)
_ensure_sqlite_compatibility()
_seed_default_admin()
