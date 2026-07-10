from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from history import record_history
from llm import convert_english_to_sql, explain_sql, fix_sql_error, optimize_sql
from models import ConnectionProfile, User
from query_engine import build_connection_string, execute_sql
from schemas import ExplainRequest, OptimizeRequest, QueryRequest
from security import get_current_user

router = APIRouter(prefix="/query", tags=["query"])


def _resolve_connection(db: Session, user_id: int, profile_id: int | None):
    if profile_id is None:
        return None, None
    profile = (
        db.query(ConnectionProfile)
        .filter(ConnectionProfile.user_id == user_id, ConnectionProfile.id == profile_id)
        .first()
    )
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection profile not found")
    connection_string = build_connection_string(
        profile.db_type,
        profile.host,
        profile.port,
        profile.database_name,
        profile.username,
        profile.password,
    )
    return profile, connection_string


@router.post("")
def generate_and_execute(
    payload: QueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile, connection_string = _resolve_connection(db, current_user.id, payload.database_profile_id)
    schema_context = ""
    if profile is not None:
        schema_context = f"Connected database: {profile.name} ({profile.db_type})"
    sql, provider = convert_english_to_sql(payload.question, provider=payload.provider)
    result: list[dict[str, Any]] = []
    if payload.execute and connection_string:
        execution = execute_sql(connection_string, sql)
        if execution.get("columns"):
            rows = execution.get("rows", [])
            result = [dict(zip(execution["columns"], row)) for row in rows]
        else:
            result = [{"status": "success", "rows_affected": execution.get("row_count", 0)}]
    record_history(
        db=db,
        user_id=current_user.id,
        question=payload.question,
        sql=sql,
        explanation=None,
        provider=provider,
        database_label=profile.name if profile else None,
        result=result,
    )
    return {
        "question": payload.question,
        "sql": sql,
        "result": result if result else [{"status": "success"}],
        "provider": provider,
        "database_label": profile.name if profile else None,
    }


@router.post("/explain")
def explain(
    payload: ExplainRequest,
    current_user: User = Depends(get_current_user),
):
    explanation, provider = explain_sql(payload.sql, provider=payload.provider)
    return {"sql": payload.sql, "explanation": explanation, "provider": provider}


@router.post("/optimize")
def optimize(
    payload: OptimizeRequest,
    current_user: User = Depends(get_current_user),
):
    optimized_sql, provider = optimize_sql(payload.sql, provider=payload.provider)
    return {"sql": payload.sql, "optimized_sql": optimized_sql, "provider": provider}

