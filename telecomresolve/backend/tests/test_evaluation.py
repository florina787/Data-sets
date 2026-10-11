def test_evaluation_release_gates(tmp_path, monkeypatch):
    """Runs the full labelled evaluation on its own isolated database."""
    import os

    from app.evaluation import run as runner

    saved = {k: os.environ.get(k) for k in ("DATABASE_URL", "CHECKPOINT_URL")}
    try:
        rep = runner.run(tmp_path)
    finally:
        for k, v in saved.items():
            os.environ[k] = v
        runner._reset_runtime()
    s = rep["summary"]
    assert s["all_gates_pass"], s["release_gates"]
    assert not s["forbidden_writes"]
    assert (tmp_path / "latest.md").exists()
