from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    full_name: str
    email: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    role: str
    is_verified: bool = False


class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: Optional[str] = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    refresh_token: Optional[str] = None
    user: UserResponse
    verification_token: Optional[str] = None


class TokenData(BaseModel):
    email: Optional[str] = None
    token_type: Optional[str] = None
    jti: Optional[str] = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class VerifyEmailRequest(BaseModel):
    token: str


class QueryRequest(BaseModel):
    question: str
    database_profile_id: Optional[int] = None
    provider: Optional[str] = None
    execute: bool = True


class ExplainRequest(BaseModel):
    sql: str
    provider: Optional[str] = None


class OptimizeRequest(BaseModel):
    sql: str
    provider: Optional[str] = None


class QueryResponse(BaseModel):
    question: str
    sql: str
    result: list[dict[str, Any]]
    provider: str
    database_label: Optional[str] = None


class ChatCreateRequest(BaseModel):
    message: str
    session_id: Optional[int] = None
    provider: Optional[str] = None
    database_profile_id: Optional[int] = None


class ChatResponse(BaseModel):
    session_id: int
    reply: str
    sql: Optional[str] = None
    provider: str


class ChatRenameRequest(BaseModel):
    title: str


class MemoryCreateRequest(BaseModel):
    text: str
    tags: Optional[str] = None


class MemoryResponse(BaseModel):
    id: int
    text: str
    tags: Optional[str] = None
    created_at: datetime


class HistoryResponse(BaseModel):
    id: int
    question: str
    sql: str
    explanation: Optional[str] = None
    provider: Optional[str] = None
    database_label: Optional[str] = None
    result_json: Optional[str] = None
    status: str
    created_at: datetime


class ConnectionProfileCreate(BaseModel):
    name: str
    db_type: str
    host: str = ""
    port: int = 0
    database_name: str
    username: str = ""
    password: str = ""


class ConnectionTestRequest(ConnectionProfileCreate):
    pass


class UploadResponse(BaseModel):
    status: str
    detail: str
    rows_affected: Optional[int] = None
