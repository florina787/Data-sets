"""Code intelligence: parse an authorised repository with tree-sitter and extract a security-relevant graph.

What is extracted (Python; JavaScript files are indexed for symbols only)
-------------------------------------------------------------------------
* modules, classes, functions (with decorators, parameters, line spans)
* imports
* calls (callee text, arguments, keyword arguments, line)
* HTTP routes from FastAPI/Flask-style decorators (``@app.get("/x")``, ``@app.route``)
* auth boundaries: a route parameter ``Depends(f)`` where ``f`` raises HTTP 401/403 (an *auth provider*)
* sinks: SQL execution, shell/process execution, file access, deserialisation, dynamic code execution
* guards: parameterised SQL, argument-list subprocess, resolved-path containment checks, owner filters in SQL
* data flow: **intraprocedural and name-based**: a parameter reaches a sink if its name (or a local assigned from it)
  occurs in the sink's arguments. This is a sound-ish approximation, not whole-program taint analysis, and every
  relationship records ``resolution`` so the UI and reports never present it as more than it is.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tree_sitter_javascript as tsjs
import tree_sitter_python as tspy
from tree_sitter import Language, Node, Parser

PY = Language(tspy.language())
JS = Language(tsjs.language())
ANALYZER = {"name": "tree-sitter", "python_grammar": "tree-sitter-python", "javascript_grammar": "tree-sitter-javascript",
            "dataflow": "intraprocedural, name-based"}
MAX_FILES = 2000
MAX_FILE_BYTES = 512_000
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".mypy_cache"}
ROUTE_METHODS = {"get", "post", "put", "delete", "patch", "route", "api_route"}

SINKS: list[tuple[str, re.Pattern[str]]] = [
    ("sql", re.compile(r"(^|\.)(execute|executemany|executescript|raw)$")),
    ("command", re.compile(r"^(subprocess\.(run|call|check_call|check_output|Popen)|os\.(system|popen|exec\w*))$")),
    ("file", re.compile(r"^(open|io\.open|send_file|FileResponse)$|\.(read_text|read_bytes|write_text|open)$")),
    ("deserialization", re.compile(r"^(pickle|cPickle|dill|marshal)\.(loads?|Unpickler)$|^yaml\.(load|unsafe_load)$")),
    ("code_exec", re.compile(r"^(eval|exec|compile)$")),
]


def _text(n: Node | None) -> str:
    return n.text.decode("utf-8", "replace") if n is not None and n.text is not None else ""


def _identifiers(n: Node) -> set[str]:
    out: set[str] = set()
    stack = [n]
    while stack:
        cur = stack.pop()
        if cur.type == "identifier":
            out.add(_text(cur))
        stack.extend(cur.children)
    return out


def _walk(n: Node):
    stack = [n]
    while stack:
        cur = stack.pop()
        yield cur
        stack.extend(reversed(cur.children))


@dataclass
class Call:
    callee: str
    line: int
    args: list[str]
    kwargs: dict[str, str]
    arg_nodes: list[Node] = field(repr=False, default_factory=list)
    identifiers: set[str] = field(default_factory=set)


@dataclass
class Function:
    name: str
    qualname: str
    file: str
    start_line: int
    end_line: int
    params: list[dict[str, str]]
    decorators: list[str]
    calls: list[Call]
    assignments: dict[str, set[str]]
    raises: list[str]
    route: dict[str, str] | None = None


@dataclass
class FileResult:
    path: str
    language: str
    sha256: str
    functions: list[Function]
    classes: list[dict[str, Any]]
    imports: list[dict[str, Any]]


def _parse_call(node: Node) -> Call:
    fn = node.child_by_field_name("function")
    args_node = node.child_by_field_name("arguments")
    args, kwargs, arg_nodes = [], {}, []
    if args_node is not None:
        for a in args_node.named_children:
            if a.type == "keyword_argument":
                kwargs[_text(a.child_by_field_name("name"))] = _text(a.child_by_field_name("value"))
            elif a.type != "comment":
                args.append(_text(a))
                arg_nodes.append(a)
    idents = _identifiers(args_node) if args_node else set()
    if fn is not None and fn.type == "attribute" and fn.child_by_field_name("object") is not None:
        idents |= _identifiers(fn.child_by_field_name("object"))  # receiver: `target.read_text()` uses `target`
    return Call(_text(fn), node.start_point[0] + 1, args, kwargs, arg_nodes, idents)


def _function(node: Node, rel: str, prefix: str, decorators: list[str]) -> Function:
    name = _text(node.child_by_field_name("name"))
    params = []
    pnode = node.child_by_field_name("parameters")
    for p in pnode.named_children if pnode else []:
        if p.type == "identifier":
            params.append({"name": _text(p), "annotation": "", "default": ""})
        elif p.type in ("typed_parameter", "default_parameter", "typed_default_parameter"):
            ident = next((c for c in p.named_children if c.type == "identifier"), None)
            params.append({"name": _text(p.child_by_field_name("name") or ident),
                           "annotation": _text(p.child_by_field_name("type")), "default": _text(p.child_by_field_name("value"))})
    body = node.child_by_field_name("body")
    calls, assignments, raises = [], {}, []
    for n in _walk(body) if body else []:
        if n.type == "call":
            calls.append(_parse_call(n))
        elif n.type == "assignment":
            left, right = n.child_by_field_name("left"), n.child_by_field_name("right")
            if left is not None and right is not None:
                for target in _identifiers(left):
                    assignments.setdefault(target, set()).update(_identifiers(right))
        elif n.type == "raise_statement":
            raises.append(_text(n))
    fn = Function(name, f"{prefix}{name}", rel, node.start_point[0] + 1, node.end_point[0] + 1, params, decorators, calls, assignments, raises)
    for d in decorators:
        m = re.match(r"@\s*([\w.]+)\.(\w+)\(\s*['\"]([^'\"]*)['\"]", d)
        if m and m.group(2) in ROUTE_METHODS:
            fn.route = {"router": m.group(1), "method": m.group(2).upper() if m.group(2) not in ("route", "api_route") else "ANY", "path": m.group(3)}
    return fn


def parse_python(rel: str, src: bytes) -> FileResult:
    tree = Parser(PY).parse(src)
    functions, classes, imports = [], [], []

    def visit(node: Node, prefix: str) -> None:
        for child in node.named_children:
            decorators: list[str] = []
            target = child
            if child.type == "decorated_definition":
                decorators = [_text(d) for d in child.named_children if d.type == "decorator"]
                target = child.child_by_field_name("definition")
            if target is None:
                continue
            if target.type == "function_definition":
                functions.append(_function(target, rel, prefix, decorators))
            elif target.type == "class_definition":
                cname = _text(target.child_by_field_name("name"))
                classes.append({"name": cname, "qualname": f"{prefix}{cname}", "start_line": target.start_point[0] + 1,
                                "end_line": target.end_point[0] + 1})
                body = target.child_by_field_name("body")
                if body is not None:
                    visit(body, f"{prefix}{cname}.")
            elif target.type in ("import_statement", "import_from_statement"):
                mod = _text(target.child_by_field_name("module_name")) if target.type == "import_from_statement" else ""
                names = [_text(n) for n in target.named_children if n.type in ("dotted_name", "aliased_import")]
                imports.append({"module": mod or (names[0] if names else ""), "names": names, "line": target.start_point[0] + 1})

    visit(tree.root_node, "")
    return FileResult(rel, "python", hashlib.sha256(src).hexdigest(), functions, classes, imports)


def parse_javascript(rel: str, src: bytes) -> FileResult:
    tree = Parser(JS).parse(src)
    functions = []
    for n in _walk(tree.root_node):
        if n.type in ("function_declaration", "method_definition"):
            name = _text(n.child_by_field_name("name"))
            functions.append(Function(name, name, rel, n.start_point[0] + 1, n.end_point[0] + 1, [], [], [], {}, []))
    return FileResult(rel, "javascript", hashlib.sha256(src).hexdigest(), functions, [], [])


def repo_files(root: Path) -> list[Path]:
    out = []
    for p in sorted(root.rglob("*")):
        if any(part in SKIP_DIRS for part in p.relative_to(root).parts) or not p.is_file() or p.is_symlink():
            continue
        if p.suffix in (".py", ".js", ".mjs", ".ts") and p.stat().st_size <= MAX_FILE_BYTES:
            out.append(p)
        if len(out) >= MAX_FILES:
            break
    return out


def git_commit(root: Path) -> tuple[str | None, bool]:
    try:
        commit = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10).stdout.strip() or None
        dirty = bool(subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--", "."], capture_output=True, text=True, timeout=10).stdout.strip())
        return commit, dirty
    except (OSError, subprocess.SubprocessError):
        return None, False


# ------------------------------------------------------------------------------------------- security semantics

def sink_category(callee: str) -> str | None:
    for cat, pat in SINKS:
        if pat.search(callee):
            return cat
    return None


def auth_providers(files: list[FileResult]) -> set[str]:
    """Functions that reject unauthenticated callers (raise 401/403)."""
    return {f.name for fr in files for f in fr.functions if any(re.search(r"\b(401|403)\b", r) for r in f.raises)}


def route_auth(fn: Function, providers: set[str]) -> list[str]:
    deps = []
    for p in fn.params:
        m = re.match(r"Depends\(\s*([\w.]+)", p["default"])
        if m and m.group(1).split(".")[-1] in providers:
            deps.append(m.group(1))
    return deps


def tainted_names(fn: Function, sources: set[str]) -> set[str]:
    tainted = set(sources)
    changed = True
    while changed:
        changed = False
        for var, deps in fn.assignments.items():
            if var not in tainted and deps & tainted:
                tainted.add(var)
                changed = True
    return tainted


def call_guards(fn: Function, call: Call, category: str) -> list[str]:
    """Deterministic, local evidence that a sink is used safely."""
    guards = []
    if category == "sql" and call.arg_nodes:
        first = call.arg_nodes[0]
        dynamic = first.type in ("binary_operator", "concatenated_string") or (first.type == "string" and _text(first).lower().startswith(("f\"", "f'")))
        dynamic = dynamic or ".format(" in call.args[0]
        if not dynamic and len(call.args) >= 2:
            guards.append("parameterised_query")
        if re.search(r"\bowner\s*=", call.args[0]) and len(call.args) >= 2:
            guards.append("owner_filter_in_query")
    if category == "command":
        if call.kwargs.get("shell", "False") != "True" and call.arg_nodes and call.arg_nodes[0].type == "list":
            guards.append("argument_list_without_shell")
    if category == "file":
        body_calls = " ".join(c.callee for c in fn.calls)
        if "resolve" in body_calls and "startswith" in body_calls:
            guards.append("resolved_path_containment_check")
    return guards


def sql_is_dynamic(call: Call) -> bool:
    if not call.arg_nodes:
        return False
    first = call.arg_nodes[0]
    return first.type in ("binary_operator", "concatenated_string") or _text(first).lower().startswith(("f\"", "f'")) or ".format(" in call.args[0]


def analyse_function(fn: Function, providers: set[str]) -> dict[str, Any]:
    """Route-level security facts used by the hypothesis engine."""
    params = {p["name"] for p in fn.params if not p["default"].startswith("Depends(")}
    tainted = tainted_names(fn, params)
    sinks = []
    for c in fn.calls:
        cat = sink_category(c.callee)
        if cat is None:
            continue
        flows = sorted(c.identifiers & tainted)
        sinks.append({"category": cat, "callee": c.callee, "line": c.line, "args": c.args[:3], "kwargs": c.kwargs,
                      "tainted_params": flows, "guards": call_guards(fn, c, cat),
                      "dynamic_sql": sql_is_dynamic(c) if cat == "sql" else None})
    return {"auth": route_auth(fn, providers), "params": sorted(params), "sinks": sinks}
