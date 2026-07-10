from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from models import MemoryEntry, User
from schemas import MemoryCreateRequest, MemoryResponse
from security import get_current_user

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("", response_model=dict)
def list_memory(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = (
        db.query(MemoryEntry)
        .filter(MemoryEntry.user_id == current_user.id, MemoryEntry.deleted_at.is_(None))
        .order_by(MemoryEntry.id.desc())
        .all()
    )
    return {
        "memory": [
            {
                "id": item.id,
                "text": item.text,
                "tags": item.tags,
                "created_at": item.created_at,
            }
            for item in items
        ]
    }


@router.post("", response_model=dict)
def add_memory(
    payload: MemoryCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Text is required")
    entry = MemoryEntry(user_id=current_user.id, text=text, tags=payload.tags)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"status": "success", "id": entry.id}


@router.get("/search", response_model=dict)
def search_memory(
    q: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    term = f"%{q.strip()}%"
    items = (
        db.query(MemoryEntry)
        .filter(
            MemoryEntry.user_id == current_user.id,
            MemoryEntry.deleted_at.is_(None),
            MemoryEntry.text.ilike(term),
        )
        .order_by(MemoryEntry.id.desc())
        .all()
    )
    return {"memory": [{"id": i.id, "text": i.text, "tags": i.tags, "created_at": i.created_at} for i in items]}


@router.delete("/{memory_id}")
def delete_memory(
    memory_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry = (
        db.query(MemoryEntry)
        .filter(MemoryEntry.user_id == current_user.id, MemoryEntry.id == memory_id)
        .first()
    )
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory item not found")
    entry.deleted_at = datetime.utcnow()
    db.commit()
    return {"status": "deleted"}
