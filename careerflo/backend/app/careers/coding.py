"""Live Coding Coach: exercises and a restricted sandbox runner.

The sandbox runs user code in a separate Python process with: AST checks (no imports outside an
allowlist, no dunder access, no open/exec/eval), CPU and memory rlimits, no inherited environment,
an empty temp working directory and a wall-clock timeout. For multi-tenant production, also run
the worker inside a locked-down container (gVisor/nsjail, no network); see docs/SECURITY.md.
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from typing import Any

EXERCISES: dict[str, dict[str, Any]] = {
    "two_sum": {"title": "Two Sum", "difficulty": "easy", "function": "two_sum",
                "prompt": "Return indices i<j such that nums[i] + nums[j] == target, or [] if none.",
                "signature": "def two_sum(nums: list[int], target: int) -> list[int]:",
                "tests": [[[[2, 7, 11, 15], 9], [0, 1]], [[[3, 2, 4], 6], [1, 2]], [[[1, 2], 7], []]]},
    "valid_parentheses": {"title": "Valid Parentheses", "difficulty": "easy", "function": "is_valid",
                          "prompt": "Return True if every bracket in s ('()[]{}') is closed in the correct order.",
                          "signature": "def is_valid(s: str) -> bool:",
                          "tests": [[["()[]{}"], True], [["(]"], False], [["([{}])"], True], [[""], True], [["(("], False]]},
    "merge_intervals": {"title": "Merge Intervals", "difficulty": "medium", "function": "merge",
                        "prompt": "Merge all overlapping [start, end] intervals and return them sorted.",
                        "signature": "def merge(intervals: list[list[int]]) -> list[list[int]]:",
                        "tests": [[[[[1, 3], [2, 6], [8, 10], [15, 18]]], [[1, 6], [8, 10], [15, 18]]], [[[[1, 4], [4, 5]]], [[1, 5]]], [[[]], []]]},
    "top_k_frequent": {"title": "Top K Frequent Words", "difficulty": "medium", "function": "top_k",
                       "prompt": "Return the k most frequent words, ties broken alphabetically.",
                       "signature": "def top_k(words: list[str], k: int) -> list[str]:",
                       "tests": [[[["i", "love", "ai", "i", "love", "code"], 2], ["i", "love"]], [[["b", "a", "b", "a", "c"], 2], ["a", "b"]]]},
    "lru_cache": {"title": "Dedupe Job Postings", "difficulty": "medium", "function": "dedupe",
                  "prompt": "Given postings as dicts with 'company' and 'title', return them with case-insensitive duplicates removed, keeping the first.",
                  "signature": "def dedupe(postings: list[dict]) -> list[dict]:",
                  "tests": [[[[{"company": "A", "title": "AI Eng"}, {"company": "a", "title": "ai eng"}, {"company": "B", "title": "X"}]],
                             [{"company": "A", "title": "AI Eng"}, {"company": "B", "title": "X"}]]]},
}

ALLOWED_IMPORTS = {"math", "collections", "heapq", "itertools", "functools", "bisect", "re", "string", "typing", "dataclasses"}
BANNED_NAMES = {"open", "exec", "eval", "compile", "__import__", "input", "globals", "locals", "vars", "getattr",
                "setattr", "delattr", "breakpoint", "help", "memoryview", "exit", "quit"}
MAX_CODE = 20_000

RUNNER = r'''
import json, resource, sys
resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
resource.setrlimit(resource.RLIMIT_NPROC, (0, 0)) if hasattr(resource, "RLIMIT_NPROC") else None
resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
spec = json.loads(sys.stdin.read())
ns = {}
exec(compile(spec["code"], "<solution>", "exec"), ns)
fn = ns.get(spec["function"])
results = []
for args, expected in spec["tests"]:
    try:
        got = fn(*json.loads(json.dumps(args)))
        results.append({"passed": got == expected, "got": repr(got)[:200], "expected": repr(expected)[:200]})
    except Exception as e:
        results.append({"passed": False, "error": f"{type(e).__name__}: {e}"[:200]})
print("__RESULT__" + json.dumps(results))
'''


class UnsafeCode(ValueError):
    pass


def check_code(code: str) -> None:
    if len(code) > MAX_CODE:
        raise UnsafeCode("Solution is too long.")
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise UnsafeCode(f"Syntax error: {exc.msg} (line {exc.lineno})") from exc
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mods = [a.name.split(".")[0] for a in node.names] if isinstance(node, ast.Import) else [(node.module or "").split(".")[0]]
            bad = [m for m in mods if m not in ALLOWED_IMPORTS]
            if bad:
                raise UnsafeCode(f"Import of {', '.join(bad)} is not allowed in the sandbox.")
        if isinstance(node, ast.Name) and node.id in BANNED_NAMES:
            raise UnsafeCode(f"Use of '{node.id}' is not allowed in the sandbox.")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise UnsafeCode("Dunder attribute access is not allowed in the sandbox.")


def run_solution(exercise_id: str, code: str, timeout: float = 6.0) -> dict[str, Any]:
    ex = EXERCISES[exercise_id]
    check_code(code)
    spec = json.dumps({"code": code, "function": ex["function"], "tests": ex["tests"]})
    with tempfile.TemporaryDirectory() as tmp:
        try:
            proc = subprocess.run([sys.executable, "-I", "-S", "-c", RUNNER], input=spec, capture_output=True,
                                  text=True, timeout=timeout, cwd=tmp, env={"PATH": "/usr/bin:/bin"},
                                  start_new_session=True)
        except subprocess.TimeoutExpired:
            return {"passed": 0, "total": len(ex["tests"]), "results": [], "error": "Time limit exceeded"}
    out = proc.stdout
    if "__RESULT__" not in out:
        err = (proc.stderr or "").strip().splitlines()
        return {"passed": 0, "total": len(ex["tests"]), "results": [],
                "error": (err[-1] if err else "Execution failed")[:300]}
    results = json.loads(out.split("__RESULT__", 1)[1])
    passed = sum(1 for r in results if r["passed"])
    return {"passed": passed, "total": len(results), "results": results, "error": None,
            "feedback": "All tests pass — now discuss time/space complexity." if passed == len(results)
            else "Some tests fail; check edge cases such as empty input and ties."}


def public_exercises() -> list[dict[str, Any]]:
    return [{"id": k, **{x: v[x] for x in ("title", "difficulty", "prompt", "signature")}, "test_count": len(v["tests"])}
            for k, v in EXERCISES.items()]


