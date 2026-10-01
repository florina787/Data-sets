"""App Builder Agent - an autonomous coding agent that builds apps from a description.

Claude plans the app, writes the files, runs commands (install, test, build) and
iterates on errors until the app works. All file and shell access is confined to
a single workspace directory.

Usage:
    python agent.py "Build a Flask todo app with SQLite and a simple HTML UI"
    python agent.py --workspace ./my_app --yes "A CLI tool that converts CSV to JSON"
    python agent.py            # interactive mode: describe the app, then keep chatting
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
COMMAND_TIMEOUT_S = 300
IGNORED_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}

SYSTEM_PROMPT = """You are an expert software engineer who builds complete, working applications.

You work inside a workspace directory using the tools provided. All paths are
relative to that workspace.

How to work:
1. Clarify the goal in your head and pick a simple, conventional stack that fits the request
   (prefer the standard library and well-known packages; avoid unnecessary dependencies).
2. Lay out the project structure, then write every file in full.
3. Install dependencies and run the app's tests or a smoke check with run_command.
   Read the errors and fix them. Repeat until it works.
4. Always include a README.md explaining how to install, run, and test the app.
5. Finish with a short summary: what you built, the file layout, and the exact commands to run it.

Commands run non-interactively with a timeout, so never start a long-running server in the
foreground; to smoke-test a server, start it in the background, probe it, then stop it
(e.g. `python app.py & PID=$!; sleep 2; curl -s localhost:5000; kill $PID`)."""


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

        @beta_tool
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

        @beta_tool
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

        @beta_tool
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

        @beta_tool
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

        @beta_tool
        def run_command(command: str) -> str:
            """Run a shell command in the workspace root and return its exit code and output.

            Use it to install dependencies, run tests, build, and smoke-test the app.
            Commands time out after 5 minutes and must not wait for keyboard input.

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
    def __init__(self, workspace: Workspace, effort: str = "high"):
        self.client = anthropic.Anthropic()
        self.workspace = workspace
        self.tools = workspace.tools()
        self.effort = effort
        self.messages: list = []  # full conversation, so follow-up requests keep context

    def send(self, user_input: str) -> None:
        self.messages.append({"role": "user", "content": user_input})
        runner = self.client.beta.messages.tool_runner(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            tools=self.tools,
            messages=self.messages,
            thinking={"type": "adaptive", "display": "summarized"},
            output_config={"effort": self.effort},
            # On a safety decline, re-run the request on Anthropic's recommended fallback model
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        for message in runner:
            # Mirror history - the runner keeps its own copy and doesn't expose it
            self.messages.append({"role": "assistant", "content": message.content})
            for block in message.content:
                if block.type == "thinking" and block.thinking:
                    print(f"\033[2m{block.thinking.strip()}\033[0m")
                elif block.type == "text":
                    print(block.text)
            if message.stop_reason == "refusal":
                print("Claude declined this request.")
            elif message.stop_reason == "max_tokens":
                print("Hit the output limit mid-response; ask the agent to continue.")
            tool_response = runner.generate_tool_call_response()  # cached; tools run once
            if tool_response is not None:
                self.messages.append(tool_response)


def main() -> None:
    parser = argparse.ArgumentParser(description="An agent that builds apps from a description.")
    parser.add_argument("request", nargs="*", help="What app to build. Omit for interactive mode.")
    parser.add_argument("--workspace", default="./generated_app", help="Directory the agent builds in.")
    parser.add_argument("--yes", action="store_true", help="Run shell commands without asking first.")
    parser.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
    args = parser.parse_args()

    workspace = Workspace(Path(args.workspace), auto_approve=args.yes)
    agent = AppBuilderAgent(workspace, effort=args.effort)
    print(f"Workspace: {workspace.root}")

    request = " ".join(args.request)
    if not request:
        request = input("What app should I build?\n> ").strip()
    try:
        while request:
            agent.send(request)
            request = input("\nAnything to change? (enter to quit)\n> ").strip()
    except (KeyboardInterrupt, EOFError):
        print()
    except anthropic.AuthenticationError:
        sys.exit("Authentication failed: set ANTHROPIC_API_KEY or run `ant auth login`.")


if __name__ == "__main__":
    main()
