import csv
import io
import os
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine


def build_connection_string(db_type: str, host: str, port: int | str, database_name: str, username: str, password: str) -> str:
    db_type = (db_type or "").lower().strip()
    if db_type == "sqlite":
        sqlite_path = database_name.strip() if database_name and database_name.strip() else "./app.db"
        return f"sqlite:///{sqlite_path}"
    if db_type == "mysql":
        return f"mysql+pymysql://{username}:{password}@{host}:{port}/{database_name}"
    if db_type == "postgresql":
        return f"postgresql+psycopg2://{username}:{password}@{host}:{port}/{database_name}"
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported database type")


def _make_engine(connection_string: str) -> Engine:
    return create_engine(
        connection_string,
        future=True,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False} if connection_string.startswith("sqlite") else {},
    )


def test_connection(connection_string: str) -> dict[str, str]:
    engine = _make_engine(connection_string)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"detail": "Connection successful"}


def execute_sql(connection_string: str, query: str) -> dict[str, Any]:
    engine = _make_engine(connection_string)
    with engine.begin() as conn:
        result = conn.execute(text(query))
        if result.returns_rows:
            rows = result.fetchall()
            columns = list(result.keys())
            return {
                "columns": columns,
                "rows": [list(row) for row in rows],
                "row_count": len(rows),
            }
        return {
            "columns": [],
            "rows": [],
            "row_count": result.rowcount if result.rowcount is not None else 0,
        }


def inspect_schema(connection_string: str, db_type: str) -> dict[str, Any]:
    engine = _make_engine(connection_string)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    details: dict[str, list[str]] = {}
    for table_name in tables:
        details[table_name] = [column["name"] for column in inspector.get_columns(table_name)]
    return {"tables": tables, "columns": details}


def import_csv(connection_string: str, table_name: str, file_bytes: bytes, if_exists: str = "replace") -> int:
    engine = _make_engine(connection_string)
    df = pd.read_csv(io.BytesIO(file_bytes))
    df.to_sql(table_name, engine, if_exists=if_exists, index=False)
    return int(df.shape[0])


def import_excel(connection_string: str, table_name: str, file_bytes: bytes, if_exists: str = "replace") -> int:
    engine = _make_engine(connection_string)
    df = pd.read_excel(io.BytesIO(file_bytes))
    df.to_sql(table_name, engine, if_exists=if_exists, index=False)
    return int(df.shape[0])


def import_sql_dump(connection_string: str, file_bytes: bytes) -> int:
    engine = _make_engine(connection_string)
    sql_text = file_bytes.decode("utf-8", errors="ignore")
    statements = [statement.strip() for statement in sql_text.split(";") if statement.strip()]
    executed = 0
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
            executed += 1
    return executed


def export_rows_to_csv(columns: list[str], rows: Iterable[Iterable[Any]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns)
    for row in rows:
        writer.writerow(list(row))
    return buffer.getvalue().encode("utf-8")
