from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from database import get_db
from models import ConnectionProfile, User
from query_engine import build_connection_string, import_csv, import_excel, import_sql_dump
from security import get_current_user

router = APIRouter(prefix="/upload", tags=["upload"])


def _latest_profile(db: Session, user_id: int) -> ConnectionProfile | None:
    return (
        db.query(ConnectionProfile)
        .filter(ConnectionProfile.user_id == user_id)
        .order_by(ConnectionProfile.id.desc())
        .first()
    )


@router.post("/csv")
async def upload_csv(
    table_name: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _latest_profile(db, current_user.id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Save a connection profile first")
    connection_string = build_connection_string(profile.db_type, profile.host, profile.port, profile.database_name, profile.username, profile.password)
    rows = import_csv(connection_string, table_name, await file.read())
    return {"status": "success", "rows_affected": rows}


@router.post("/excel")
async def upload_excel(
    table_name: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _latest_profile(db, current_user.id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Save a connection profile first")
    connection_string = build_connection_string(profile.db_type, profile.host, profile.port, profile.database_name, profile.username, profile.password)
    rows = import_excel(connection_string, table_name, await file.read())
    return {"status": "success", "rows_affected": rows}


@router.post("/sql-dump")
async def upload_sql_dump(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _latest_profile(db, current_user.id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Save a connection profile first")
    connection_string = build_connection_string(profile.db_type, profile.host, profile.port, profile.database_name, profile.username, profile.password)
    statements = import_sql_dump(connection_string, await file.read())
    return {"status": "success", "statements_executed": statements}

