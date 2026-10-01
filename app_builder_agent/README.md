# App Builder Agent

An autonomous agent, powered by Claude, that builds a complete **full-stack web app for any subject**.
Give it a subject, such as "library management", "gym class booking" or "recipe sharing". It plans
the app and builds all three tiers. Then it installs dependencies, runs the tests and starts the
app to check it end to end, fixing anything that fails.

## What it builds

Every generated app has the same three-tier layout:

| Folder | Tier | Contents |
|---|---|---|
| `frontend/` | Frontend (presentation) | Responsive web UI: dashboard, list views with search, detail pages, create/edit forms, delete confirmations, and loading/empty/error states. All network calls go through one API client module. |
| `api/` | Middle tier | REST API under `/api` (CRUD for every entity plus actions specific to the subject), request validation, a service layer for business rules, and middleware for CORS, request logging and central error handling. Includes `GET /api/health`. In production it also serves the built frontend on the same port. |
| `backend/` | Backend (data) | Database connection, models for every entity, data-access functions (the only code that touches the database), schema setup and realistic seed data. |

Requests flow `frontend → api → backend → database`. The frontend never touches the database, and the
data tier never handles HTTP.

The agent also writes:
- `PLAN.md`: features, entities and relationships, business rules, API endpoints and pages, written before any code
- tests for the data tier and the API
- `README.md` and `run.sh` for the generated app

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # or: ant auth login
```

The default stack also needs Node.js (for React). Without Node, use `--stack fastapi-vanilla`.

## Usage

```bash
# Build an app about any subject
python agent.py "library management"

# Pick the stack and folder; skip the confirmation before each shell command
python agent.py --stack fastapi-vanilla --workspace ./clinic --yes "veterinary clinic"

# Interactive: give a subject, then ask for changes ("add user login", "add a stats page")
python agent.py
```

| Flag | Default | Meaning |
|---|---|---|
| `--stack` | `fastapi-react` | Technologies for the three tiers (see below). |
| `--workspace` | `./generated_app` | Directory the agent builds in. It can't read or write outside it. |
| `--yes` | off | Run shell commands without asking first. |
| `--effort` | `high` | How hard Claude thinks: `low`, `medium`, `high`, `xhigh` or `max`. |

### Stacks

| `--stack` | Backend (data) | Middle tier | Frontend |
|---|---|---|---|
| `fastapi-react` | Python, SQLAlchemy, SQLite | FastAPI + Pydantic | React + Vite |
| `fastapi-vanilla` | Python, SQLAlchemy, SQLite | FastAPI + Pydantic | Plain HTML/CSS/JS (no Node needed) |
| `express-react` | Node.js, better-sqlite3 | Express + zod | React + Vite |
| `auto` | Claude picks the stack that best fits the subject | | |

## How the agent works

1. **Plan:** expands the subject into a realistic feature set and writes `PLAN.md`.
2. **Build:** writes the backend, then the middle tier, then the frontend.
3. **Test:** writes and runs tests for the data tier and the API.
4. **Verify:** installs dependencies, runs the tests and builds the frontend. It then starts the
   app in the background, calls the health, list and create endpoints, loads the frontend page and
   stops the server. It fixes and re-runs anything that fails.
5. **Document:** writes the app's README and `run.sh`, then prints a summary.

Under the hood:
- **Model:** `claude-opus-5-5` with adaptive thinking. Reasoning summaries are shown dimmed.
- **Loop:** the Anthropic SDK's streaming tool runner, with a 64K-token output limit per response
  so large files fit. If a response is cut off mid-file, the agent tells Claude to split the file
  and carries on.
- **Tools** (all limited to the workspace): `write_file`, `read_file`, `edit_file`, `list_files`,
  and `run_command` (10-minute timeout; long output is shortened).
- **Memory:** the conversation is kept, so follow-up requests change the existing app.
- **Refusal fallback:** if Claude's safety checks decline a request, it is retried on
  Anthropic's recommended fallback model.

## Safety

Shell commands run on your machine. Path checks stop the file tools from leaving the workspace.
Shell commands, though, can reach anything your user account can. Leave `--yes` off unless the
agent is running in a container or VM you don't mind it changing.
