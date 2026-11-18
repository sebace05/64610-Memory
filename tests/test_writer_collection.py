"""Offline writer collection checks; fixture counts are never Qwen evidence."""
from dataclasses import asdict
import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from game_memory import memory_probe as mp
from game_memory import writer_collection as wc
from test_memory_probe import FixtureModel, _rewrite


@pytest.fixture
def family():
    return wc.generate_splits()["calibration"][0]


@pytest.fixture
def package(tmp_path):
    path = tmp_path / "package"
    wc.prepare(path)
    return path


def test_explicit_rng_builder_preserves_v1_construction_without_mutating_v1():
    before = mp.digest(mp.generate_splits())
    for index in (0, 1):
        old = "blue" if index == 0 else None
        actual = wc._build_family(mp.stream("dev", index, "family", 0),
            mp.stream("dev", index, "options"), f"D{index:02d}", "dev", index, old, set(), 0)
        assert actual == mp._family("dev", index, old, set(), 0)
    assert mp.digest(mp.generate_splits()) == before


def test_fresh_families_are_deterministic_disjoint_and_balanced():
    splits = wc.generate_splits()
    assert splits == wc.generate_splits()
    wc.check_splits(splits)
    legacy = [f for fs in mp.generate_splits().values() for f in fs]
    fresh = [f for fs in splits.values() for f in fs]
    legacy_names = {n for f in legacy for n in [*f["order"], *f["pulses"]]}
    fresh_names = [n for f in fresh for n in [*f["order"], *f["pulses"]]]
    assert len(fresh) == 60 and len(fresh_names) == len(set(fresh_names)) == 1200
    assert not legacy_names & set(fresh_names)
    assert not {mp._composition(f) for f in legacy} & {mp._composition(f) for f in fresh}
    for split, families in splits.items():
        assert sum(f["query_type"] == "updated" for f in families) == len(families) // 2
        for f in families:
            for world in f["worlds"]:
                assert len(world["observations"]) == 14
                assert mp.public_state(world["observations"])["state"][f["roles"]["target"]] == world["answer"]
        olds = [f["base"][f["roles"]["target"]] for f in families if f["query_type"] == "updated"]
        assert len(set(olds)) == min(4, len(olds))


@pytest.mark.parametrize("fault", ["allocation", "stratum", "world", "legacy_name"])
def test_split_checks_reject_changes(fault):
    splits = wc.generate_splits()
    f = splits["calibration"][0]
    if fault == "allocation":
        f["family_id"] = "C99"
    elif fault == "stratum":
        f["query_type"] = "untouched"
    elif fault == "world":
        f["worlds"][0]["world"] = 3
    else:
        f["pulses"][0] = mp.generate_splits()["dev"][0]["order"][0]
    with pytest.raises(ValueError):
        wc.check_splits(splits)


def test_package_freezes_sources_splits_and_refuses_overwrite(package):
    manifest = wc.verify_package(package, source=Path.cwd())
    assert manifest["request_ceiling"] == 896
    assert manifest["splits"]["test"]["family_ids"] == [f"E{i:02d}" for i in range(16)]
    with pytest.raises(FileExistsError):
        wc.prepare(package)
    (package / "splits/test.json").write_text("[]")
    with pytest.raises(ValueError, match="split bytes"):
        wc.verify_package(package)


def test_package_detects_source_changes(package, tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    import zipfile
    with zipfile.ZipFile(package / "source.zip") as archive:
        archive.extractall(source)
    (source / "game_memory/writer_collection.py").write_text("changed")
    with pytest.raises(ValueError, match="current writer source"):
        wc.verify_package(package, source=source)


def test_family_exports_literal_states_without_reader_calls_or_hidden_labels(family, tmp_path):
    model = FixtureModel()
    out = tmp_path / "C00"
    commits = []
    audit = wc.write_family(family, 256, out, model, commit=lambda: commits.append(model.calls))
    assert audit == {"unit": "C00", "requests": 112, "reader_calls": 0, "writes": 112,
                     "assessments": 0, "snapshots": 16}
    assert commits == [112]
    writes = wc._rows(out / "writes.jsonl")
    snapshots = wc._rows(out / "snapshots.jsonl")
    inputs = wc._rows(out / "reader-inputs.jsonl")
    for s, reader in zip(snapshots, inputs):
        original = next(w for w in writes if (w["world"], w["format"], w["write_index"])
                        == (s["world"], s["format"], mp.PROBES[s["probe"]]))
        assert s["rendered"] == original["rendered"]
        assert s["token_count"] == model.count_tokens(s["rendered"])
        assert reader["messages"] == [asdict(m) for m in mp.reader_messages(
            s["rendered"], family["roles"]["target"], family["options"])]
        assert reader["supported_label"] is None and "gold" not in reader
    for e in wc._rows(out / "events.jsonl"):
        if e["event"] == "model_request":
            assert e["purpose"] == "memory"
            assert set(json.loads(e["messages"][1]["content"])) == mp.WRITER_FIELDS


def test_writer_requests_ignore_future_query_options_and_gold(family, tmp_path):
    changed = copy.deepcopy(family)
    changed["roles"]["target"] = family["order"][-1]
    changed["options"] = list(reversed(family["options"]))
    for world in changed["worlds"]:
        world["answer"] = "hidden sentinel"
    requests = []
    for i, f in enumerate((family, changed)):
        out = tmp_path / str(i)
        wc.write_family(f, 256, out, FixtureModel(), commit=lambda: None)
        requests.append([e["messages"] for e in wc._rows(out / "events.jsonl")
                         if e["event"] == "model_request"])
    assert requests[0] == requests[1]
    assert wc._rows(tmp_path / "0/reader-inputs.jsonl") != wc._rows(tmp_path / "1/reader-inputs.jsonl")


@pytest.mark.parametrize("fault", ["missing", "duplicate", "text", "count", "id", "label", "prompt", "metadata"])
def test_export_audit_rejects_falsified_data_even_when_rehashed(family, tmp_path, fault):
    out = tmp_path / "family"
    wc.write_family(family, 256, out, FixtureModel(), commit=lambda: None)
    name = "snapshots.jsonl" if fault in {"missing", "duplicate", "text", "count", "id"} else "reader-inputs.jsonl"
    def change(rows):
        if fault == "missing":
            rows.pop()
        elif fault == "duplicate":
            rows[-1] = rows[0]
        else:
            key, value = {"text": ("rendered", "invented"), "count": ("token_count", 999),
                "id": ("snapshot_id", "incorrect"), "label": ("supported_label", "A"),
                "prompt": ("messages", []), "metadata": ("allowance", 128)}[fault]
            rows[0][key] = value
        return rows
    _rewrite(out, name, change)
    with pytest.raises(mp.AuditError):
        wc.audit_family(out, family, 256, real=False)


@pytest.mark.parametrize("size,expected", [(0, 128), (128, 128), (129, 256), (256, 256)])
def test_budget_rule_uses_all_64_snapshots_and_includes_empty(size, expected):
    assert wc.select_allowance([0] * 63 + [size]) == expected


@pytest.mark.parametrize("counts", [[128] * 63, [128] * 65, [True] * 64, [-1] * 64, [257] * 64])
def test_incomplete_or_invalid_counts_do_not_select_a_budget(counts):
    with pytest.raises(ValueError):
        wc.select_allowance(counts)


def test_calibration_loads_once_commits_families_and_recounts_every_snapshot(package, tmp_path):
    model, loads, durable = FixtureModel(), [], []
    out = tmp_path / "run"
    def loader(*args):
        loads.append(args)
        return model, model.count_tokens
    def commit():
        durable.append((model.calls, sorted(p.parent.name for p in out.glob("C*/completion.json"))))
    result = wc.calibrate(package, out, loader=loader, commit=commit)
    assert len(loads) == 1 and model.calls == 448
    assert durable[:5] == [(0, []), (112, ["C00"]), (224, ["C00", "C01"]),
                          (336, ["C00", "C01", "C02"]), (448, ["C00", "C01", "C02", "C03"])]
    assert result["complete"] and result["status"]["model_is_fake"]
    assert result["selected_allowance"] == 128 and len(result["snapshots"]) == 64
    assert result["known_usage"]["primary_calls"] == 448
    assert result["known_usage"]["repair_calls"] == 0
    assert result["known_usage"]["input_tokens"] == 4480
    assert wc._read(out / "snapshot-recount.json")["evidence"] == "synthetic_fixture"
    assert not list(out.glob("E*")) and not list(out.glob("R*"))
    with pytest.raises(FileExistsError):
        wc.calibrate(package, out, loader=loader, commit=commit)
    assert len(loads) == 1


def test_invalid_candidates_repair_once_fallback_exactly_and_count_empty_snapshots(package, tmp_path):
    # Over-budget prose and malformed JSON: neither is semantically rescued.
    model = FixtureModel(writer=lambda payload, fmt, purpose: "x" * 2000)
    out = tmp_path / "run"
    result = wc.calibrate(package, out, loader=lambda *_: (model, model.count_tokens), commit=lambda: None)
    assert model.calls == 896
    assert result["known_usage"]["primary_calls"] == result["known_usage"]["repair_calls"] == 448
    for fmt in mp.FORMATS:
        assert result["cells"][fmt]["fallbacks"] == result["cells"][fmt]["repairs"] == 224
        assert result["cells"][fmt]["empty_snapshots"] == 32
    assert result["selected_allowance"] == 128  # Not a claim that these empty notes are useful.


@pytest.mark.parametrize("failure", ["inference", "recount", "deadline"])
def test_failure_preserves_partial_work_and_never_fabricates_budget(package, tmp_path, failure):
    model = FixtureModel(fail_after=2 if failure == "inference" else None)
    wall = [0]
    def loader(*args):
        if failure == "deadline":
            wall[0] = wc.SOFT_SECONDS + 1
        return model, lambda text: model.count_tokens(text) + (failure == "recount")
    out = tmp_path / "run"
    with pytest.raises((RuntimeError, mp.AuditError)):
        wc.calibrate(package, out, loader=loader, commit=lambda: None, clock=lambda: wall[0])
    result = wc.report(out)
    assert not result["complete"] and result["selected_allowance"] is None
    assert not (out / "calibration-decision.json").exists() and not (out / "completion.json").exists()
    if failure == "inference":
        assert result["known_usage"]["responses"] == 2
        assert result["known_usage"]["unknown_usage_requests"] == 1
        assert not (out / "C00/completion.json").exists()
    elif failure == "recount":
        assert len(result["audits"]) == 4
    else:
        assert model.calls == 0


def test_status_cleanup_does_not_replace_original_model_error(package, tmp_path, monkeypatch):
    save = wc.transport.save
    def fail(path, value):
        if path.name == "status.json":
            raise OSError("fixture disk failure")
        return save(path, value)
    monkeypatch.setattr(wc.transport, "save", fail)
    model = FixtureModel(fail_after=0)
    with pytest.raises(RuntimeError, match="synthetic transport failure") as raised:
        wc.calibrate(package, tmp_path / "run", loader=lambda *_: (model, model.count_tokens), commit=lambda: None)
    assert "fixture disk failure" in str(raised.value.__notes__)


def test_guard_forbids_reader_calls_and_stops_at_the_ceiling():
    model = FixtureModel()
    guard = wc._WriterOnly(model, float("inf"), lambda: 0)
    with pytest.raises(ValueError, match="forbids"):
        guard.generate([], purpose="action")
    with pytest.raises(ValueError, match="forbids"):
        guard.score_choices([], labels=mp.LABELS)
    guard.calls = wc.REQUEST_CEILING
    with pytest.raises(RuntimeError, match="ceiling"):
        guard.generate([], purpose="memory")
    assert model.calls == 0


def test_import_and_help_are_offline():
    code = """import sys
from game_memory import writer_collection
assert not {'torch', 'transformers', 'modal'} & set(sys.modules)
sys.argv=['writer-collection','--help']
writer_collection.main()
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0 and "calibrate" in result.stdout


def test_explicit_recovery_copies_complete_units_and_generates_only_missing_families(package, tmp_path):
    first = FixtureModel()
    original = tmp_path / "original"
    wc.calibrate(package, original, loader=lambda *_: (first, first.count_tokens), commit=lambda: None)
    manifest = wc._read(original / "entry.json")["manifest"]
    reuse = [{"family_id": fid, "directory": str(original / fid),
              "source_manifest_sha256": manifest["manifest_sha256"],
              "completion_sha256": mp.file_sha256(original / fid / "completion.json")}
             for fid in ("C00", "C01")]
    second = FixtureModel()
    recovered = tmp_path / "recovered"
    result = wc.calibrate(package, recovered, loader=lambda *_: (second, second.count_tokens),
                          commit=lambda: None, reuse=reuse)
    assert result["complete"] and second.calls == 224
    assert result["status"]["new_attempted_requests"] == 224
    assert result["status"]["reused_requests"] == 224
    assert result["status"]["attempted_requests"] == result["known_usage"]["responses"] == 448
    assert result["selected_allowance"] == 128
    for item in reuse:
        for path in (original / item["family_id"]).iterdir():
            assert (recovered / item["family_id"] / path.name).read_bytes() == path.read_bytes()


@pytest.mark.parametrize("fault", ["hash", "source", "incomplete", "duplicate"])
def test_recovery_refuses_bad_or_incomplete_sources_before_model_load(package, tmp_path, fault):
    model = FixtureModel()
    original = tmp_path / "original"
    wc.calibrate(package, original, loader=lambda *_: (model, model.count_tokens), commit=lambda: None)
    item = {"family_id": "C00", "directory": str(original / "C00"),
            "source_manifest_sha256": wc._read(original / "entry.json")["manifest"]["manifest_sha256"],
            "completion_sha256": mp.file_sha256(original / "C00/completion.json")}
    reuse = [item]
    if fault == "hash":
        item["completion_sha256"] = "0" * 64
    elif fault == "source":
        item["source_manifest_sha256"] = "0" * 64
    elif fault == "incomplete":
        (original / "C00/completion.json").unlink()
    else:
        reuse.append(item)
    with pytest.raises((mp.AuditError, FileNotFoundError)):
        wc.calibrate(package, tmp_path / "recovery", loader=lambda *_: pytest.fail("bad recovery reached model load"),
                     commit=lambda: None, reuse=reuse)
