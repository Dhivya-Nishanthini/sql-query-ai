from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from history import save_query
from models import User
from security import get_current_user

router = APIRouter(prefix="/queries", tags=["queries"])


@router.post("/save")
def save_query_alias(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return save_query(payload, current_user=current_user, db=db)

