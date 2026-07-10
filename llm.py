import json
import os
import re
from typing import Optional

import requests

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DEFAULT_LLM_PROVIDER = os.getenv("DEFAULT_LLM_PROVIDER", "openai").lower().strip()


def _normalize_provider(provider: Optional[str]) -> str:
    selected = (provider or DEFAULT_LLM_PROVIDER or "").lower().strip()
    if selected in {"openai", "gemini"}:
        return selected
    if OPENAI_API_KEY:
        return "openai"
    if GEMINI_API_KEY:
        return "gemini"
    return "local"


def _openai_chat(prompt: str, system: str) -> str:
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def _gemini_chat(prompt: str) -> str:
    response = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        params={"key": GEMINI_API_KEY},
        json={
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.9,
                "maxOutputTokens": 700,
            },
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def _local_generate_sql(question: str) -> str:
    q = question.lower()
    if "join" in q:
        return "SELECT a.*, b.* FROM table_a a JOIN table_b b ON a.id = b.a_id;"
    if "count" in q or "how many" in q:
        return "SELECT COUNT(*) AS total_count FROM table_name;"
    if "top" in q or "highest" in q or "largest" in q:
        return "SELECT * FROM table_name ORDER BY metric DESC LIMIT 10;"
    if "group" in q or "by" in q:
        return "SELECT category, COUNT(*) AS total FROM table_name GROUP BY category;"
    return "SELECT 1;"


def _local_explain_sql(sql: str) -> str:
    normalized = sql.strip().rstrip(";")
    if not normalized:
        return "No SQL was provided."
    if re.search(r"\bjoin\b", normalized, re.IGNORECASE):
        return "This query combines rows from two or more tables using a join condition."
    if re.search(r"\bgroup\s+by\b", normalized, re.IGNORECASE):
        return "This query groups rows into aggregates based on one or more columns."
    if re.search(r"\border\s+by\b", normalized, re.IGNORECASE):
        return "This query sorts the results using the specified order."
    return "This query retrieves data from the database using SQL."


def _local_optimize_sql(sql: str) -> str:
    optimized = sql.strip()
    if not optimized:
        return "SELECT 1;"
    if not optimized.endswith(";"):
        optimized += ";"
    return optimized


def generate_sql(question: str, provider: Optional[str] = None, schema_context: str = "") -> tuple[str, str]:
    selected = _normalize_provider(provider)
    prompt = (
        "Generate a single SQL query for the user request. "
        "Return only SQL, no markdown.\n\n"
        f"Schema context:\n{schema_context or 'None provided'}\n\n"
        f"User request: {question}"
    )
    if selected == "openai" and OPENAI_API_KEY:
        return _openai_chat(prompt, "You are a precise SQL assistant."), "openai"
    if selected == "gemini" and GEMINI_API_KEY:
        return _gemini_chat(prompt), "gemini"
    if selected == "openai" and not OPENAI_API_KEY and GEMINI_API_KEY:
        return _gemini_chat(prompt), "gemini"
    if selected == "gemini" and not GEMINI_API_KEY and OPENAI_API_KEY:
        return _openai_chat(prompt, "You are a precise SQL assistant."), "openai"
    return _local_generate_sql(question), "local"


def explain_sql(sql: str, provider: Optional[str] = None) -> tuple[str, str]:
    selected = _normalize_provider(provider)
    prompt = (
        "Explain the following SQL in concise, user-friendly English. "
        "Return a short explanation only.\n\n"
        f"SQL:\n{sql}"
    )
    if selected == "openai" and OPENAI_API_KEY:
        return _openai_chat(prompt, "You explain SQL clearly and concisely."), "openai"
    if selected == "gemini" and GEMINI_API_KEY:
        return _gemini_chat(prompt), "gemini"
    return _local_explain_sql(sql), "local"


def optimize_sql(sql: str, provider: Optional[str] = None) -> tuple[str, str]:
    selected = _normalize_provider(provider)
    prompt = (
        "Optimize the following SQL query for readability and performance. "
        "Return only the optimized SQL.\n\n"
        f"SQL:\n{sql}"
    )
    if selected == "openai" and OPENAI_API_KEY:
        return _openai_chat(prompt, "You optimize SQL and return only SQL."), "openai"
    if selected == "gemini" and GEMINI_API_KEY:
        return _gemini_chat(prompt), "gemini"
    return _local_optimize_sql(sql), "local"


def convert_english_to_sql(text: str, provider: Optional[str] = None) -> tuple[str, str]:
    return generate_sql(text, provider=provider)


def convert_sql_to_english(sql: str, provider: Optional[str] = None) -> tuple[str, str]:
    return explain_sql(sql, provider=provider)


def fix_sql_error(question: str, error_message: str, provider: Optional[str] = None) -> tuple[str, str]:
    selected = _normalize_provider(provider)
    prompt = (
        "Fix the SQL query issue described by the user. "
        "Return a corrected SQL query only.\n\n"
        f"User question: {question}\n"
        f"Database error: {error_message}"
    )
    if selected == "openai" and OPENAI_API_KEY:
        return _openai_chat(prompt, "You repair SQL queries and return only SQL."), "openai"
    if selected == "gemini" and GEMINI_API_KEY:
        return _gemini_chat(prompt), "gemini"
    return _local_generate_sql(question), "local"

def provider_status() -> dict[str, bool | str]:
    return {
        "default": _normalize_provider(None),
        "openai": bool(OPENAI_API_KEY),
        "gemini": bool(GEMINI_API_KEY),
    }

