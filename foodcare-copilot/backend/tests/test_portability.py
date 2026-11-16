"""Cross-platform process handling and small copilot UX rules."""

from __future__ import annotations

import os
import subprocess
import sys
import time

import psutil

from app.copilot import engine, router
from app.tools import deploy

from conftest import user


def test_alive_is_a_pure_check_and_only_recognises_the_storefront():
    # A process that is not the storefront is reported as not ours, and is left running.
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert deploy._alive(proc.pid) is False
        assert proc.poll() is None  # the check did not signal or kill it
        assert deploy._alive(os.getpid()) is False
    finally:
        proc.kill()
        proc.wait()
    assert deploy._alive(proc.pid) is False  # gone


def test_stop_tree_stops_a_process_and_its_children():
    code = ("import subprocess,sys,time; "
            "subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); time.sleep(30)")
    proc = subprocess.Popen([sys.executable, "-c", code], start_new_session=os.name == "posix")
    for _ in range(50):
        if psutil.Process(proc.pid).children():
            break
        time.sleep(0.05)
    kids = psutil.Process(proc.pid).children(recursive=True)
    deploy._signal_tree(proc.pid, force=True)
    proc.wait(timeout=5)
    gone, alive = psutil.wait_procs(kids, timeout=5)
    assert not alive


def test_greeting_gets_a_friendly_help_answer(platform):
    for hello in ("Hi", "hii", "Hi there, how are you?", "hey whats up", "who are you", "Hi Jerry 👋", "Namaste",
                  "good evening team", "thanks!"):
        assert router.parse(hello).intents == ["help"], hello
    assert router.parse("What is the weather in Paris?").intents == []  # still declined, not small talk
    assert router.parse("Hi, how did our sales do in the last 4 weeks?").intents == ["sales"]
    answer = engine.ask("Hi", user("val.viewer"))
    assert answer["answer"].startswith("Hi! I'm Jerry") and "global supply chain" in answer["answer"]
    assert "can't answer" not in answer["answer"]
    assert engine.ask("how are you?", user("val.viewer"))["answer"].startswith("Hi! I'm Jerry, FoodCare's read-only "
                                                                           "copilot. I'm running well")
    assert engine.ask("thanks!", user("val.viewer"))["answer"].startswith("You're welcome!")
