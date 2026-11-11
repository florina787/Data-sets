# Instructions for GitHub Copilot

The main application in this repository is `foodcare-copilot/` (Flo & Jerry — Food Copilot 2.0).
Follow `foodcare-copilot/.github/copilot-instructions.md` for how to run it and the rules to respect.
Run its commands from inside `foodcare-copilot/` (for example `cd foodcare-copilot && scripts/start.sh`).
Never download language or vision models, never start a second model server, and never push without the user's request.
Use branch `claude/new-session-pahp8j` (the default branch has no `foodcare-copilot/`). On Windows, run every command in
Git Bash, not PowerShell. Python must be 3.13 (pinned in `foodcare-copilot/.python-version`), never 3.14 or 3.15.

**Terminal rule (Windows):** the workspace sets Git Bash as the default terminal (`.vscode/settings.json`).
Run ONE simple command per terminal call, directly in that Git Bash terminal. NEVER wrap bash inside PowerShell
(no `& 'C:\Program Files\Git\bin\bash.exe' -lc '...'`): PowerShell strips the inner quotes and bash fails with
"unexpected end of file". Avoid multi-line `if ... fi` one-liners; use plain commands such as `ls`, `cat FILE`, `cd DIR`.
If the terminal is still PowerShell, stop and ask the user to reload VS Code (Developer: Reload Window).
