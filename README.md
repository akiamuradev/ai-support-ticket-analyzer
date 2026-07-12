# AI Support Ticket Analyzer

Portfolio web application for analyzing customer support tickets with an LLM.

The app lets a user paste a customer message, analyze it with a temporary stub,
and store recent results in SQLite.

## Features

- FastAPI backend
- Temporary deterministic analysis stub
- SQLite ticket history
- Pydantic request and response schemas
- Static HTML, CSS, and JavaScript frontend
- Consistent JSON error responses
- Pytest API and repository tests
- Docker and Docker Compose setup

## Project Structure

```text
ai-support-ticket-analyzer/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── schemas.py
│   ├── database.py
│   ├── repository.py
│   ├── llm.py
│   ├── prompts.py
│   └── services.py
├── static/
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── tests/
│   └── test_api.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## API

- `GET /health`
- `POST /api/tickets/analyze`
- `GET /api/tickets?limit=20`
- `GET /api/tickets/{ticket_id}`
- `DELETE /api/tickets/{ticket_id}`
- `GET /`

Example analysis request:

```bash
curl -X POST http://127.0.0.1:8000/api/tickets/analyze \
  -H "Content-Type: application/json" \
  -d '{"text":"Customer cannot log in after changing their password."}'
```

Successful responses include:

- `id`
- `original_text`
- `category`
- `priority`
- `summary`
- `suggested_reply`
- `created_at`

Validation and runtime errors use this shape:

```json
{
  "error": "Request validation failed"
}
```

## Environment

```env
APP_ENV=development
APP_URL=http://127.0.0.1:8000
OPENROUTER_API_KEY=
OPENROUTER_MODEL=openai/gpt-4o-mini
OPENROUTER_TIMEOUT_SECONDS=30
DATABASE_URL=sqlite:///./support_tickets.db
```

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

The current stage uses a local stub analyzer and does not call OpenRouter.

Open the app at http://127.0.0.1:8000/.

## Tests

```bash
pytest
```

Tests use a fake analyzer and a temporary SQLite database, so they do not call
OpenRouter.

## Docker

```bash
docker compose up --build
```

Open the app at http://127.0.0.1:8000/.
