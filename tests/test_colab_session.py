"""The live session keeps weights, but rejects code changes between requests."""

import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from game_memory.colab_session import ColabSession, serve


def test_session_loads_once_and_refuses_changed_source(monkeypatch, capsys):
    loaded, calls = [], []

    def load(config):
        loaded.append(config)
        return SimpleNamespace(config=config, metadata={"load_seconds": 1})

    def run(arguments, *, model):
        calls.append((arguments, model))
        return 0

    sources = iter([{"commit": "original"}, {"commit": "original"}, {"commit": "changed"}])
    monkeypatch.setattr("game_memory.colab_session.source_metadata", lambda: next(sources))
    monkeypatch.setattr("game_memory.transformers_model.TransformersModel", load)
    monkeypatch.setattr("game_memory.run_episode.main", run)
    monkeypatch.setattr("sys.stdin", io.StringIO(
        json.dumps({"revision": "a" * 40}) + '\n["--seed", "0"]\n["--seed", "1"]\n'))
    assert serve() == 0
    captured = capsys.readouterr()
    replies = [json.loads(s) for s in captured.out.splitlines()]
    assert replies[0]["ready"] and len(loaded) == len(calls) == 1
    assert replies[1:] == [{"returncode": 0}, {"returncode": 1}]
    assert "Repository changed" in captured.err


def test_startup_failure_is_returned_and_preserved_without_starting_a_game(tmp_path):
    log = tmp_path / "session.log"
    with pytest.raises(RuntimeError, match="immutable 40-character"):
        ColabSession(sys.executable, Path(__file__).resolve().parents[1],
                     {"revision": "main"}, log)
    assert "ValueError" in log.read_text()
    assert not list(tmp_path.glob("*/events.jsonl"))
