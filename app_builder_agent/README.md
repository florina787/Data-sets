# App Builder Agent

An autonomous agent, powered by Claude, that builds working apps from a plain-English description.
It plans the project, writes the files, installs dependencies, runs tests and smoke checks,
and fixes errors until the app works.

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # or: ant auth login
```

## Usage

```bash
# One-shot: describe the app
python agent.py "Build a Flask todo app with SQLite and a simple HTML UI"

# Choose the output folder; skip the confirmation before each shell command
python agent.py --workspace ./csv2json --yes "A CLI that converts CSV files to JSON, with tests"

# Interactive: describe the app, then ask for changes
python agent.py
```

Options:

| Flag | Default | Meaning |
|---|---|---|
| `--workspace` | `./generated_app` | Directory the agent builds in. It can't read or write outside it. |
| `--yes` | off | Run shell commands without asking first. |
| `--effort` | `high` | How hard Claude thinks: `low`, `medium`, `high`, `xhigh` or `max`. |

## How it works

- **Model:** `claude-opus-5-5` with adaptive thinking. Reasoning summaries are shown dimmed.
- **Loop:** the Anthropic SDK's tool runner (`client.beta.messages.tool_runner`) calls Claude,
  runs the tools Claude asks for, sends back the results, and repeats until Claude is done.
- **Tools** (all limited to the workspace):
  - `write_file`, `read_file`, `edit_file`, `list_files`: work with project files
  - `run_command`: runs shell commands such as installs, tests and builds. It has a 5-minute
    timeout, and long output is cut down before it goes back to Claude.
- **Memory:** the conversation is kept, so follow-up requests in interactive mode build on
  the earlier work.
- **Refusal fallback:** server-side `fallbacks: "default"` is on. If Claude's safety
  classifiers decline a request, it is retried on Anthropic's recommended fallback model.

## Safety

Shell commands run on your machine. Path checks stop the file tools from leaving the workspace.
Shell commands, though, can reach anything your user account can. Leave `--yes` off unless the
agent is running in a container or VM you don't mind it changing.
