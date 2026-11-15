"""Failure guards for the held-out grid launcher."""

import json

import pytest

from game_memory.evaluate_3x2 import completed_seeds, source_digest


def _result(root, episode, seed, status="completed"):
    directory = root / episode
    directory.mkdir()
    (directory / "events.jsonl").write_text("{}\n")
    (directory / "result.json").write_text(json.dumps({
        "status": status, "config": {"seed": seed},
    }))


def test_completed_seeds_rejects_duplicate_and_error_results(tmp_path):
    _result(tmp_path, "one", 1000)
    assert completed_seeds(tmp_path) == {1000}
    _result(tmp_path, "two", 1000)
    with pytest.raises(ValueError, match="Duplicate seed"):
        completed_seeds(tmp_path)
    (tmp_path / "two" / "result.json").unlink()
    with pytest.raises(ValueError, match="Partial episode"):
        completed_seeds(tmp_path)
    _result(tmp_path, "three", 1001, "error")
    with pytest.raises(ValueError, match="Infrastructure error"):
        completed_seeds(tmp_path)


def test_source_digest_detects_executable_change(tmp_path):
    (tmp_path / "game_memory").mkdir()
    (tmp_path / "game_memory" / "runner.py").write_text("before")
    for name in ("requirements.txt", "requirements-model.txt", "AGENTS.md"):
        (tmp_path / name).write_text(name)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "experiment-3x2-protocol.md").write_text("protocol")
    before = source_digest(tmp_path)
    (tmp_path / "game_memory" / "runner.py").write_text("after")
    assert source_digest(tmp_path) != before
