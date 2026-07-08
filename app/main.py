import os
from datetime import datetime, timedelta
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import Column, Integer, String, create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from pydantic import BaseModel
import requests
import json

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
SECRET_KEY = os.getenv("SECRET_KEY", "super-secret")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DEFAULT_LLM_PROVIDER = os.getenv("DEFAULT_LLM_PROVIDER", "openai")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

app = FastAPI(title="SQL Genius AI", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="user")
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    updated_at = Column(String, default=lambda: datetime.utcnow().isoformat())


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, nullable=False)
    role = Column(String, nullable=False)
    content = Column(String, nullable=False)
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())


class SavedQuery(Base):
    __tablename__ = "saved_queries"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    query = Column(String, nullable=False)
    explanation = Column(String, nullable=True)
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())


class ConnectionProfile(Base):
    __tablename__ = "connection_profiles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    name = Column(String, nullable=False)
    db_type = Column(String, nullable=False)
    host = Column(String, nullable=False)
    port = Column(Integer, nullable=False)
    database_name = Column(String, nullable=False)
    username = Column(String, nullable=False)
    password = Column(String, nullable=False)
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())


Base.metadata.create_all(bind=engine)


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: str | None = None


class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str




class ChatRequest(BaseModel):
    message: str
    mode: str = "chat"


class ConnectionRequest(BaseModel):
    db_type: str
    host: str
    port: str
    database_name: str
    username: str
    password: str


class QueryExecutionRequest(ConnectionRequest):
    query: str


class SaveQueryRequest(BaseModel):
    title: str
    query: str
    explanation: str | None = None


# dependency helpers

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def ensure_default_admin_user() -> User:
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == "admin@example.com").first()
        if admin is None:
            admin = User(
                email="admin@example.com",
                full_name="Administrator",
                password_hash=get_password_hash("admin123"),
                role="admin"
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
        elif not verify_password("admin123", admin.password_hash):
            admin.password_hash = get_password_hash("admin123")
            db.commit()
        return admin
    finally:
        db.close()


ensure_default_admin_user()


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def authenticate_user(db: Session, email: str, password: str):
    user = db.query(User).filter(User.email == email).first()

    if not user:
        return None

    ok = verify_password(password, user.password_hash)

    if not ok:
        return None

    return user

def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str | None = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.email == token_data.email).first()
    if user is None:
        raise credentials_exception
    return user


@app.get("/")
def read_root():
    return {"message": "SQL Genius AI API is running"}





@app.post("/auth/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = authenticate_user(db, form_data.username, form_data.password)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password"
        )

    access_token = create_access_token(
        data={"sub": user.email}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role
        }
    }


@app.get("/auth/me")
def me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email, "full_name": current_user.full_name, "role": current_user.role}


@app.post("/chat/ask")
def chat_ask(req: ChatRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    reply = generate_sql_reply(req.message)
    session = db.query(ChatSession).filter(ChatSession.user_id == current_user.id).order_by(ChatSession.id.desc()).first()
    if session is None:
        session = ChatSession(user_id=current_user.id, title=req.message[:40])
        db.add(session)
        db.commit()
        db.refresh(session)
    db.add(ChatMessage(session_id=session.id, role="user", content=req.message))
    db.add(ChatMessage(session_id=session.id, role="assistant", content=reply))
    db.commit()
    return {"reply": reply, "session_id": session.id}


@app.get("/chat/history")
def chat_history(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sessions = db.query(ChatSession).filter(ChatSession.user_id == current_user.id).order_by(ChatSession.id.desc()).all()
    saved = db.query(SavedQuery).filter(SavedQuery.user_id == current_user.id).order_by(SavedQuery.id.desc()).all()
    return {"sessions": [{"id": s.id, "title": s.title, "created_at": s.created_at} for s in sessions], "saved_queries": [{"id": q.id, "title": q.title, "query": q.query, "explanation": q.explanation} for q in saved]}


@app.post("/queries/save")
def save_query(payload: SaveQueryRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = SavedQuery(user_id=current_user.id, title=payload.title, query=payload.query, explanation=payload.explanation)
    db.add(query)
    db.commit()
    return {"message": "saved"}


@app.post("/connections/test")
def test_connection(payload: ConnectionRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        engine = create_engine(build_connection_string(payload), connect_args={"check_same_thread": False} if payload.db_type == "sqlite" else {})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"detail": f"Connection successful to {payload.db_type}"}
    except Exception as exc:
        return {"detail": f"Connection failed: {exc}"}


@app.post("/connections/execute")
def execute_query(payload: QueryExecutionRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        engine = create_engine(build_connection_string(payload), connect_args={"check_same_thread": False} if payload.db_type == "sqlite" else {})
        with engine.connect() as conn:
            result = conn.execute(text(payload.query))
            rows = result.fetchall()
            columns = list(result.keys())
        return {"columns": columns, "rows": [list(row) for row in rows]}
    except Exception as exc:
        return {"detail": str(exc)}


@app.post("/connections/schema")
def inspect_schema(payload: ConnectionRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        engine = create_engine(build_connection_string(payload), connect_args={"check_same_thread": False} if payload.db_type == "sqlite" else {})
        with engine.connect() as conn:
            if payload.db_type == "sqlite":
                result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"))
                tables = [row[0] for row in result.fetchall()]
            elif payload.db_type == "mysql":
                result = conn.execute(text("SHOW TABLES"))
                tables = [row[0] for row in result.fetchall()]
            else:
                result = conn.execute(text("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname != 'pg_catalog' AND schemaname != 'information_schema' ORDER BY tablename"))
                tables = [row[0] for row in result.fetchall()]
        return {"tables": tables}
    except Exception as exc:
        return {"detail": str(exc)}


def build_connection_string(req: ConnectionRequest) -> str:
    if req.db_type == "sqlite":
        return f"sqlite:///{req.database_name}"
    if req.db_type == "mysql":
        return f"mysql+pymysql://{req.username}:{req.password}@{req.host}:{req.port}/{req.database_name}"
    if req.db_type == "postgresql":
        return f"postgresql+psycopg2://{req.username}:{req.password}@{req.host}:{req.port}/{req.database_name}"
    raise ValueError("Unsupported database type")


def generate_sql_reply(prompt: str) -> str:
    prompt_lower = prompt.lower()
    if "join" in prompt_lower:
        fallback = "A JOIN combines rows from related tables based on a shared key. For example, `SELECT e.name, d.name FROM employees e INNER JOIN departments d ON e.department_id = d.id;` returns only matching rows."
    elif "select" in prompt_lower or "query" in prompt_lower:
        fallback = "A well-formed query usually starts with `SELECT`, narrows results with `WHERE`, and can group or sort them with `GROUP BY` and `ORDER BY`."
    else:
        fallback = "I can help with SQL generation, explanation, optimization, debugging, and database execution. The external AI provider is temporarily unavailable, so I’m providing a concise fallback response instead."

    if OPENAI_API_KEY:
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "system", "content": "You are SQL Genius AI, an expert SQL assistant. Provide concise, accurate SQL guidance with examples and explain concepts clearly."}, {"role": "user", "content": prompt}],
                    "temperature": 0.2,
                },
                timeout=20,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception:
            return fallback
    if GEMINI_API_KEY:
        try:
            response = requests.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=" + GEMINI_API_KEY,
                json={
                    "contents": [
                        {
                            "role": "user",
                            "parts": [
                                {
                                    "text": (
                                        "You are SQL Genius AI, an expert SQL assistant. "
                                        "Provide a concise, accurate explanation with a simple example.\n\n"
                                        f"User prompt: {prompt}"
                                    )
                                }
                            ],
                        }
                    ],
                    "generationConfig": {"temperature": 0.2, "topP": 0.9, "maxOutputTokens": 400},
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            return fallback
    return fallback
