# SQL Genius AI

SQL Genius AI is a production-ready AI SQL assistant with a React + Vite frontend and a FastAPI backend. It supports:

- JWT authentication
- ChatGPT-style SQL assistance
- SQL generation, explanation, debugging, and optimization
- SQLite/MySQL/PostgreSQL connection testing and query execution
- Saved queries and chat history

## Tech stack

- Backend: FastAPI, SQLAlchemy, Python 3.12
- Frontend: React, Vite, Tailwind, Framer Motion, React Icons
- AI: OpenAI or Gemini API
- Database: SQLite (default), MySQL, PostgreSQL

## Run locally

### Backend

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
npm install
npm run dev
```

Visit http://localhost:5173

## Environment variables

Copy .env.example to .env and fill values.

## Docker

```bash
docker compose up --build
```
