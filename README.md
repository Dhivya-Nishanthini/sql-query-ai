# SQL Query AI

Production-ready FastAPI + React SQL assistant with JWT auth, refresh tokens, AI SQL generation, query execution, chat history, persistent memory, database connections, and upload/import support.

## Stack

- Backend: FastAPI, SQLAlchemy, Alembic, Python 3.11
- Auth: JWT, refresh tokens, Passlib bcrypt, python-jose
- AI: OpenAI API or Gemini API
- Frontend: React, Vite, Tailwind CSS
- Databases: SQLite, PostgreSQL, MySQL

## Environment

Copy `.env.example` to `.env` and set:

- `DATABASE_URL`
- `SECRET_KEY`
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `DEFAULT_LLM_PROVIDER`

## Run locally

### Backend

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
npm install
npm run dev
```

## API

- `POST /auth/signup`
- `POST /auth/login`
- `GET /auth/me`
- `POST /auth/logout`
- `POST /auth/refresh`
- `POST /auth/verify-email`
- `POST /auth/forgot-password`
- `POST /auth/reset-password`
- `POST /query`
- `POST /query/explain`
- `POST /query/optimize`
- `GET /history`
- `GET /history/{id}`
- `GET /memory`
- `POST /memory`
- `POST /chat`
- `GET /chat/{id}`
- `GET /connections/profiles`
- `POST /connections/test`
- `POST /connections/execute`
- `POST /connections/schema`

## Deployment

- Render: use `render.yaml`
- Docker: `docker build -t sql-query-ai .`

