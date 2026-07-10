import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from models import HistoryEntry, SavedQuery, User
from schemas import HistoryResponse
from security import get_current_user

router = APIRouter(prefix="/history", tags=["history"])


def record_history(
    db: Session,
    user_id: int,
    question: str,
    sql: str,
    explanation: str | None = None,
    provider: str | None = None,
    database_label: str | None = None,
    result: Any | None = None,
    status_value: str = "success",
) -> HistoryEntry:
    entry = HistoryEntry(
        user_id=user_id,
        question=question,
        sql=sql,
        explanation=explanation,
        provider=provider,
        database_label=database_label,
        result_json=json.dumps(result, default=str) if result is not None else None,
        status=status_value,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("", response_model=list[HistoryResponse])
def list_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    offset = (page - 1) * page_size
    rows = (
        db.query(HistoryEntry)
        .filter(HistoryEntry.user_id == current_user.id)
        .order_by(HistoryEntry.id.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return rows


@router.get("/{history_id}", response_model=HistoryResponse)
def get_history_item(
    history_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry = (
        db.query(HistoryEntry)
        .filter(HistoryEntry.user_id == current_user.id, HistoryEntry.id == history_id)
        .first()
    )
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="History item not found")
    return entry


@router.post("/save")
def save_query(
    payload: dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    title = str(payload.get("title") or "Saved Query").strip()
    query = str(payload.get("query") or "").strip()
    explanation = payload.get("explanation")
    if not query:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query is required")
    saved = SavedQuery(
        user_id=current_user.id,
        title=title,
        query=query,
        explanation=explanation,
        provider=payload.get("provider"),
        database_label=payload.get("database_label"),
    )
    db.add(saved)
    db.commit()
    db.refresh(saved)
    return {"status": "saved", "id": saved.id}


@router.post("/queries/save")
def save_query_legacy(
    payload: dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return save_query(payload, current_user=current_user, db=db)
