"""App Builder Agent - builds a complete full-stack app for any subject.

Give it a subject ("library management", "gym class booking", "recipe sharing") and
Claude plans the app, then builds all three tiers:

    backend/   data tier     - database models, repositories, schema and seed data
    api/       middle tier   - REST API, validation, business rules, middleware
    frontend/  presentation  - the web UI that talks to the API

It installs dependencies, runs the tests, starts the app and checks it end to end,
fixing errors until everything works. All file and shell access is confined to a
single workspace directory.

Usage:
    python agent.py "library management"
    python agent.py --stack fastapi-vanilla --workspace ./clinic --yes "veterinary clinic"
    python agent.py            # interactive mode: give a subject, then ask for changes
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import anthropic
from anthropic import beta_tool

MODEL = "claude-opus-5-5"
MAX_OUTPUT_CHARS = 20_000  # truncate long command output before it goes back to Claude
COMMAND_TIMEOUT_S = 600
MAX_RETRIES = 3
IGNORED_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}

STACKS = {
    "fastapi-react": (
        "Data tier: Python, SQLAlchemy 2.x, SQLite. Middle tier: FastAPI with Pydantic v2 schemas. "
        "Presentation tier: React + Vite (JavaScript). If `node --version` fails, fall back to the "
        "fastapi-vanilla stack and say so."
    ),
    "fastapi-vanilla": (
        "Data tier: Python, SQLAlchemy 2.x, SQLite. Middle tier: FastAPI with Pydantic v2 schemas. "
        "Presentation tier: plain HTML, CSS and JavaScript modules (no build step, no Node) served "
        "by FastAPI as static files."
    ),
    "express-react": (
        "Data tier: Node.js with better-sqlite3. Middle tier: Express with zod validation. "
        "Presentation tier: React + Vite (JavaScript)."
    ),
    "auto": "Choose the most suitable conventional stack for the subject and explain the choice in PLAN.md.",
}

SYSTEM_PROMPT = """You are a senior full-stack engineer. Given any subject, you design and build a complete,
working, three-tier web application for it, using the tools provided. All paths are relative to the
workspace root.

<architecture>
Every app has exactly these three tiers, each in its own top-level folder:

backend/   DATA TIER
  - Database connection and session handling, ORM models / table definitions for every entity
  - Repository (data-access) functions: the only code that talks to the database
  - Schema creation on startup and a seed script with realistic sample data for the subject

api/       MIDDLE TIER (sits between frontend and backend)
  - REST endpoints under /api: full CRUD for every entity, plus search/filter and the
    subject-specific actions the app needs (e.g. "borrow a book", "book a class")
  - Request/response schemas with validation; consistent JSON errors {"error": {"code", "message"}}
  - Service layer holding the business rules; routes stay thin and call services, services call
    backend repositories
  - Middleware: CORS, request logging with timing, central error handling; a GET /api/health endpoint
  - In production mode it also serves the built frontend, so the whole app runs on one port

frontend/  PRESENTATION TIER
  - A clean, responsive UI: navigation, a dashboard/home page, list views with search, detail views,
    create/edit forms with client-side validation, delete with confirmation
  - Every network call goes through one API client module (e.g. frontend/src/api.js)
  - Loading, empty and error states everywhere; no placeholder or lorem-ipsum content
  - In development, the dev server proxies /api to the middle tier

The frontend never touches the database, and the data tier never handles HTTP.
</architecture>

<process>
1. Plan. Expand the subject into a realistic feature set. Write PLAN.md with: features, entities with
   fields and relationships, business rules, every API endpoint (method, path, purpose), every page,
   and the folder layout. Keep the scope achievable: 3-6 core entities.
2. Build the data tier, then the middle tier, then the presentation tier. Write files in full.
   Keep files focused and reasonably small (split large components and modules).
3. Write tests: data-tier and API tests (e.g. pytest + FastAPI TestClient against a temporary
   database, or the equivalent for the stack) covering CRUD, validation errors and business rules.
4. Verify, and fix anything that fails, until all of these pass:
   - dependencies install cleanly
   - all tests pass
   - the frontend builds (if it has a build step)
   - end-to-end smoke test: start the app in the background, call GET /api/health and at least one
     list and one create endpoint with curl, request the frontend's index page, then stop the server
5. Write README.md (what the app does, the three-tier layout, setup, run in dev and production,
   test commands, API endpoint table) and a run script (run.sh) that installs, seeds and starts the app.
6. Finish with a short summary: what you built, the layout, verification results, and how to run it.
</process>

<rules>
- Commands run non-interactively with a timeout. Never run a server in the foreground; for smoke
  tests use the background pattern, e.g. `(uvicorn api.main:app --port 8765 &> /tmp/srv.log &) ;
  sleep 3; curl -sf localhost:8765/api/health; pkill -f "port 8765"`.
- Don't use interactive scaffolders (they wait for input); write package.json and config files yourself.
- Use a Python virtual environment (.venv) for Python dependencies, and pin versions in
  requirements.txt / package.json.
- If a command fails, read the error, fix the cause and re-run; don't move on with something broken.
</rules>"""


class Workspace:
    """File and shell tools scoped to one directory."""

    def __init__(self, root: Path, auto_approve: bool):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.auto_approve = auto_approve

    def resolve(self, path: str) -> Path:
        target = (self.root / path).resolve()
        if target != self.root and self.root not in target.parents:
            raise ValueError(f"Path '{path}' escapes the workspace")
        return target

    def tools(self) -> list:
        ws = self

        @beta_tool(eager_input_streaming=True)
        def write_file(path: str, content: str) -> str:
            """Create or overwrite a file in the workspace with the full content given.

            Args:
                path: File path relative to the workspace root, e.g. "src/app.py".
                content: The complete file content.
            """
            target = ws.resolve(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            log("write", f"{path} ({len(content)} chars)")
            return f"Wrote {path}"

        @beta_tool(eager_input_streaming=True)
        def read_file(path: str) -> str:
            """Read a text file from the workspace.

            Args:
                path: File path relative to the workspace root.
            """
            target = ws.resolve(path)
            if not target.is_file():
                return f"Error: {path} does not exist"
            log("read", path)
            return target.read_text(encoding="utf-8", errors="replace")

        @beta_tool(eager_input_streaming=True)
        def edit_file(path: str, old_text: str, new_text: str) -> str:
            """Replace one exact, unique occurrence of old_text with new_text in a file.

            Args:
                path: File path relative to the workspace root.
                old_text: Exact text to find; must occur exactly once in the file.
                new_text: Replacement text.
            """
            target = ws.resolve(path)
            if not target.is_file():
                return f"Error: {path} does not exist"
            text = target.read_text(encoding="utf-8")
            count = text.count(old_text)
            if count != 1:
                return f"Error: old_text found {count} times in {path}; it must match exactly once"
            target.write_text(text.replace(old_text, new_text), encoding="utf-8")
            log("edit", path)
            return f"Edited {path}"

        @beta_tool(eager_input_streaming=True)
        def list_files(path: str = ".") -> str:
            """List files under a workspace directory, recursively (skips .git, node_modules, venvs).

            Args:
                path: Directory relative to the workspace root. Defaults to the root.
            """
            base = ws.resolve(path)
            if not base.is_dir():
                return f"Error: {path} is not a directory"
            files = [
                str(p.relative_to(ws.root))
                for p in sorted(base.rglob("*"))
                if p.is_file() and not IGNORED_DIRS.intersection(p.relative_to(ws.root).parts)
            ]
            return "\n".join(files) or "(empty)"

        @beta_tool(eager_input_streaming=True)
        def run_command(command: str) -> str:
            """Run a shell command in the workspace root and return its exit code and output.

            Use it to install dependencies, run tests, build, and smoke-test the app.
            Commands time out after 10 minutes and must not wait for keyboard input.

            Args:
                command: The shell command to run, e.g. "pip install -r requirements.txt && pytest -q".
            """
            log("run", command)
            if not ws.auto_approve:
                answer = input("    Allow this command? [y/N] ").strip().lower()
                if answer not in ("y", "yes"):
                    return "The user declined to run this command. Try another approach or ask them."
            try:
                proc = subprocess.run(
                    command, shell=True, cwd=ws.root, capture_output=True, text=True,
                    timeout=COMMAND_TIMEOUT_S, stdin=subprocess.DEVNULL,
                )
            except subprocess.TimeoutExpired:
                return f"Error: command timed out after {COMMAND_TIMEOUT_S}s"
            output = (proc.stdout + proc.stderr).strip()
            if len(output) > MAX_OUTPUT_CHARS:
                output = output[:MAX_OUTPUT_CHARS // 2] + "\n...[truncated]...\n" + output[-MAX_OUTPUT_CHARS // 2:]
            return f"exit code: {proc.returncode}\n{output}"

        return [write_file, read_file, edit_file, list_files, run_command]


def log(kind: str, detail: str) -> None:
    print(f"  \033[36m[{kind}]\033[0m {detail}", flush=True)


class AppBuilderAgent:
    def __init__(self, workspace: Workspace, stack: str = "fastapi-react", effort: str = "high"):
        self.client = anthropic.Anthropic()
        self.workspace = workspace
        self.tools = workspace.tools()
        self.system = f"{SYSTEM_PROMPT}\n\n<stack>\n{STACKS[stack]}\n</stack>"
        self.effort = effort
        self.messages: list = []  # full conversation, so follow-up requests keep context

    def build(self, subject: str) -> None:
        self.send(
            f"Build a complete three-tier web app (backend, middle-tier API, frontend) for this "
            f"subject: {subject}"
        )

    def send(self, user_input: str) -> None:
        turn_start = len(self.messages)
        self.messages.append({"role": "user", "content": user_input})
        retries = 0
        while True:
            try:
                if self._run():
                    return
            except ValueError as err:
                # Tool input that couldn't be parsed: restart from the mirrored history,
                # dropping an assistant turn whose tool calls never got results
                if self.messages[-1]["role"] == "assistant":
                    self.messages.pop()
                retries += 1
                if retries > MAX_RETRIES:
                    raise
                print(f"Retrying after malformed tool input: {err}")
            else:
                # Claude declined: drop this turn so the conversation stays valid
                del self.messages[turn_start:]
                return

    def _run(self) -> bool:
        """Run the tool loop from the current history. Returns False if Claude declined."""
        runner = self.client.beta.messages.tool_runner(
            model=MODEL,
            max_tokens=64000,
            system=self.system,
            tools=self.tools,
            messages=self.messages,
            thinking={"type": "adaptive", "display": "summarized"},
            output_config={"effort": self.effort},
            # On a safety decline, re-run the request on Anthropic's recommended fallback model
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            stream=True,
        )
        for stream in runner:
            message = stream.get_final_message()
            # Mirror history - the runner keeps its own copy and doesn't expose it
            self.messages.append({"role": "assistant", "content": message.content})
            for block in message.content:
                if block.type == "thinking" and block.thinking:
                    print(f"\033[2m{block.thinking.strip()}\033[0m")
                elif block.type == "text":
                    print(block.text)

            if message.stop_reason == "refusal":
                print("Claude declined this request.")
                return False
            tool_uses = [b for b in message.content if b.type == "tool_use"]
            if message.stop_reason == "max_tokens" and tool_uses:
                # The last tool call was cut off: don't run it, tell Claude, and continue
                self.messages.append({"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": t.id, "is_error": True,
                     "content": "Not run: the response hit the output limit. Write smaller files "
                                "(split them up) and try again."}
                    for t in tool_uses
                ]})
                return self._run()

            tool_response = runner.generate_tool_call_response()  # cached; tools run once
            if tool_response is not None:
                self.messages.append(tool_response)
        return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Builds a full-stack three-tier app for any subject.")
    parser.add_argument("subject", nargs="*", help='What the app is about, e.g. "library management".')
    parser.add_argument("--workspace", default="./generated_app", help="Directory the agent builds in.")
    parser.add_argument("--stack", default="fastapi-react", choices=list(STACKS),
                        help="Technology stack for the three tiers.")
    parser.add_argument("--yes", action="store_true", help="Run shell commands without asking first.")
    parser.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
    args = parser.parse_args()

    workspace = Workspace(Path(args.workspace), auto_approve=args.yes)
    agent = AppBuilderAgent(workspace, stack=args.stack, effort=args.effort)
    print(f"Workspace: {workspace.root}\nStack: {args.stack}")

    subject = " ".join(args.subject) or input("What subject should the app be about?\n> ").strip()
    try:
        if subject:
            agent.build(subject)
            while change := input("\nAnything to change? (enter to quit)\n> ").strip():
                agent.send(change)
    except (KeyboardInterrupt, EOFError):
        print()
    except anthropic.AuthenticationError:
        sys.exit("Authentication failed: set ANTHROPIC_API_KEY or run `ant auth login`.")


if __name__ == "__main__":
    main()
