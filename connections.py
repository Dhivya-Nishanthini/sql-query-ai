from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from database import get_db
from models import ConnectionProfile, User
from schemas import ConnectionProfileCreate, ConnectionTestRequest, UploadResponse
from security import get_current_user
from llm import provider_status
from query_engine import (
    build_connection_string,
    execute_sql,
    import_csv,
    import_excel,
    import_sql_dump,
    inspect_schema,
    test_connection,
)

router = APIRouter(prefix="/connections", tags=["connections"])


@router.post("/test")
def test_db_connection(
    payload: ConnectionTestRequest,
    current_user: User = Depends(get_current_user),
):
    connection_string = build_connection_string(
        payload.db_type,
        payload.host,
        payload.port,
        payload.database_name,
        payload.username,
        payload.password,
    )
    result = test_connection(connection_string)
    result["provider_status"] = provider_status()
    return result


@router.post("/execute")
def execute_db_query(
    payload: dict,
    current_user: User = Depends(get_current_user),
):
    connection_string = build_connection_string(
        payload.get("db_type", "sqlite"),
        payload.get("host", ""),
        payload.get("port", 0),
        payload.get("database_name", ""),
        payload.get("username", ""),
        payload.get("password", ""),
    )
    query = str(payload.get("query") or "").strip()
    if not query:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query is required")
    return execute_sql(connection_string, query)


@router.post("/schema")
def get_schema(
    payload: ConnectionTestRequest,
    current_user: User = Depends(get_current_user),
):
    connection_string = build_connection_string(
        payload.db_type,
        payload.host,
        payload.port,
        payload.database_name,
        payload.username,
        payload.password,
    )
    return inspect_schema(connection_string, payload.db_type)


@router.get("/profiles")
def list_profiles(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profiles = db.query(ConnectionProfile).filter(ConnectionProfile.user_id == current_user.id).all()
    return [
        {
            "id": profile.id,
            "name": profile.name,
            "db_type": profile.db_type,
            "host": profile.host,
            "port": profile.port,
            "database_name": profile.database_name,
            "username": profile.username,
            "created_at": profile.created_at,
        }
        for profile in profiles
    ]


@router.post("/profiles")
def save_profile(
    payload: ConnectionProfileCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = ConnectionProfile(
        user_id=current_user.id,
        name=payload.name.strip(),
        db_type=payload.db_type,
        host=payload.host,
        port=payload.port,
        database_name=payload.database_name,
        username=payload.username,
        password=payload.password,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return {"status": "saved", "id": profile.id}


@router.post("/import/csv", response_model=UploadResponse)
async def import_csv_file(
    table_name: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(ConnectionProfile).filter(ConnectionProfile.user_id == current_user.id).order_by(ConnectionProfile.id.desc()).first()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Save a connection profile first")
    connection_string = build_connection_string(profile.db_type, profile.host, profile.port, profile.database_name, profile.username, profile.password)
    rows = import_csv(connection_string, table_name, await file.read())
    return UploadResponse(status="success", detail="CSV imported", rows_affected=rows)


@router.post("/import/excel", response_model=UploadResponse)
async def import_excel_file(
    table_name: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(ConnectionProfile).filter(ConnectionProfile.user_id == current_user.id).order_by(ConnectionProfile.id.desc()).first()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Save a connection profile first")
    connection_string = build_connection_string(profile.db_type, profile.host, profile.port, profile.database_name, profile.username, profile.password)
    rows = import_excel(connection_string, table_name, await file.read())
    return UploadResponse(status="success", detail="Excel imported", rows_affected=rows)


@router.post("/import/sql-dump", response_model=UploadResponse)
async def import_sql_dump_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(ConnectionProfile).filter(ConnectionProfile.user_id == current_user.id).order_by(ConnectionProfile.id.desc()).first()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Save a connection profile first")
    connection_string = build_connection_string(profile.db_type, profile.host, profile.port, profile.database_name, profile.username, profile.password)
    statements = import_sql_dump(connection_string, await file.read())
    return UploadResponse(status="success", detail="SQL dump imported", rows_affected=statements)

