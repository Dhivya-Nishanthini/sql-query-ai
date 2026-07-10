import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from llm import generate_sql
from models import ChatMessage, ChatSession, SavedQuery, User
from schemas import ChatCreateRequest, ChatRenameRequest, ChatResponse
from security import get_current_user
from history import record_history

router = APIRouter(prefix="/chat", tags=["chat"])


def _get_or_create_session(db: Session, user_id: int, title: str, provider: str) -> ChatSession:
    session = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user_id, ChatSession.deleted_at.is_(None))
        .order_by(ChatSession.id.desc())
        .first()
    )
    if session is None:
        session = ChatSession(user_id=user_id, title=title[:80] or "New Chat", provider=provider)
        db.add(session)
        db.commit()
        db.refresh(session)
    return session


@router.get("")
def list_chats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id, ChatSession.deleted_at.is_(None))
        .order_by(ChatSession.id.desc())
        .all()
    )
    return {
        "sessions": [
            {
                "id": session.id,
                "title": session.title,
                "provider": session.provider,
                "created_at": session.created_at,
                "updated_at": session.updated_at,
            }
            for session in sessions
        ]
    }


@router.get("/history")
def chat_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id, ChatSession.deleted_at.is_(None))
        .order_by(ChatSession.id.desc())
        .all()
    )
    saved = (
        db.query(SavedQuery)
        .filter(SavedQuery.user_id == current_user.id)
        .order_by(SavedQuery.id.desc())
        .all()
    )
    return {
        "sessions": [
            {
                "id": session.id,
                "title": session.title,
                "created_at": session.created_at,
                "updated_at": session.updated_at,
            }
            for session in sessions
        ],
        "saved_queries": [
            {
                "id": item.id,
                "title": item.title,
                "query": item.query,
                "explanation": item.explanation,
                "provider": item.provider,
                "database_label": item.database_label,
                "created_at": item.created_at,
            }
            for item in saved
        ],
    }


@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message is required")
    provider = payload.provider or "openai"
    session = _get_or_create_session(db, current_user.id, message, provider)
    sql, used_provider = generate_sql(message, provider=provider)
    reply = f"Generated SQL:\n\n{sql}"
    db.add(ChatMessage(session_id=session.id, role="user", content=message))
    db.add(ChatMessage(session_id=session.id, role="assistant", content=reply, sql=sql))
    session.title = session.title or message[:80]
    session.provider = used_provider
    db.commit()
    record_history(
        db=db,
        user_id=current_user.id,
        question=message,
        sql=sql,
        explanation=reply,
        provider=used_provider,
        database_label=None,
        result=[],
    )
    return {"session_id": session.id, "reply": reply, "sql": sql, "provider": used_provider}


@router.post("/ask")
def chat_ask(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    message = str(payload.get("message") or "").strip()
    provider = payload.get("provider")
    session_id = payload.get("session_id")
    if not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message is required")
    if session_id:
        session = (
            db.query(ChatSession)
            .filter(ChatSession.id == int(session_id), ChatSession.user_id == current_user.id, ChatSession.deleted_at.is_(None))
            .first()
        )
        if session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    else:
        session = _get_or_create_session(db, current_user.id, message, provider or "openai")
    sql, used_provider = generate_sql(message, provider=provider)
    reply = f"Generated SQL:\n\n{sql}"
    db.add(ChatMessage(session_id=session.id, role="user", content=message))
    db.add(ChatMessage(session_id=session.id, role="assistant", content=reply, sql=sql))
    session.title = session.title or message[:80]
    session.provider = used_provider
    db.commit()
    record_history(
        db=db,
        user_id=current_user.id,
        question=message,
        sql=sql,
        explanation=reply,
        provider=used_provider,
        database_label=None,
        result=[],
    )
    return {"reply": reply, "session_id": session.id, "sql": sql, "provider": used_provider}


@router.get("/{chat_id}")
def get_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == chat_id, ChatSession.user_id == current_user.id, ChatSession.deleted_at.is_(None))
        .first()
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.id.asc())
        .all()
    )
    return {
        "id": session.id,
        "title": session.title,
        "provider": session.provider,
        "messages": [
            {
                "id": message.id,
                "role": message.role,
                "content": message.content,
                "sql": message.sql,
                "created_at": message.created_at,
            }
            for message in messages
        ],
    }


@router.patch("/{chat_id}/rename")
def rename_chat(
    chat_id: int,
    payload: ChatRenameRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == chat_id, ChatSession.user_id == current_user.id, ChatSession.deleted_at.is_(None))
        .first()
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    session.title = payload.title.strip()[:120] or session.title
    session.updated_at = datetime.utcnow()
    db.commit()
    return {"status": "renamed"}


@router.delete("/{chat_id}")
def delete_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == chat_id, ChatSession.user_id == current_user.id, ChatSession.deleted_at.is_(None))
        .first()
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    session.deleted_at = datetime.utcnow()
    db.commit()
    return {"status": "deleted"}
