"""Offline ablation checks. Synthetic scores/token counts are not Qwen results."""
import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from game_memory import name_ablation as na
from test_reader_diagnostic import FixtureModel, Tokenizer, note_state


@pytest.fixture
def package(tmp_path):
    path = tmp_path / "package"
    na.prepare(path)
    return path


class NoGeneration(FixtureModel):
    def generate(self, *args, **kwargs):
        pytest.fail("ablation attempted generation/writing")


def test_fixed_selection_variants_and_physical_schedule():
    entries, provenance = na.cases()
    assert entries == na.cases()[0]
    assert len(entries) == 256 and len({c["prompt_sha256"] for c in entries}) == 248
    assert len({(c["prompt_sha256"], m) for c, m in na.schedule(entries)}) == 280
    assert len(na.schedule(entries)) == 296
    assert len({c["variant"] for c in entries if c["family_id"] == "Q00"}) == 16
    assert {c["family_id"] for c in entries} == {"Q00", "Q01", "Q02"}
    assert provenance["kind"].startswith("reconstructed")
    assert all(m == "repeat" for _, m in na.schedule(entries)[-8:])


def test_interventions_preserve_gold_options_and_exactly_the_declared_change():
    entries, _ = na.cases()
    indexed = {(c["family_id"], c["world"], c["format"], c["variant"]): c for c in entries}
    for c in entries:
        base = indexed[c["family_id"], c["world"], c["format"], "matched_lexical"]
        assert c["gold"] == base["gold"] and c["options"] == base["options"]
        assert c["state"][c["query"]] == c["gold"]
        assert note_state(c["memory"]) == c["state"]
        r = c["distractor_roles"]
        assert len(set(r.values()) | {base["query"]}) == 5
        assert base["state"][r["suspect"]] == base["state"][r["control"]]
        if c["renames"]:
            assert len(c["renames"]) == 1 and not c["value_changes"]
            assert c["entity_order"] == [c["renames"].get(n, n) for n in base["entity_order"]]
            assert list(c["state"].values()) == list(base["state"].values())
            assert c["query"] == c["renames"].get(base["query"], base["query"])
            old = next(iter(c["renames"]))
            assert old not in c["messages"][1]["content"].lower()
        elif c["value_changes"]:
            assert len(c["value_changes"]) == 1
            assert c["query"] not in c["value_changes"]
            assert c["entity_order"] == base["entity_order"]
            assert {n for n in c["state"] if c["state"][n] != base["state"][n]} == set(c["value_changes"])
        elif c["variant"].startswith("swap_"):
            assert c["state"] == base["state"]
            assert sum(a != b for a, b in zip(c["entity_order"], base["entity_order"])) == 2
        assert c["messages"] == [na.asdict(m) for m in na.mp.reader_messages(c["memory"], c["query"], c["options"])]


def test_direct_format_comparisons_match_record_order():
    entries, _ = na.cases()
    indexed = {(c["family_id"], c["world"], c["format"], c["variant"]): c for c in entries}
    for c in entries:
        if c["variant"] != "original":
            other = indexed[c["family_id"], c["world"], "json" if c["format"] == "prose" else "prose", c["variant"]]
            assert other["entity_order"] == c["entity_order"] and other["state"] == c["state"]


def test_value_controls_match_destination_histograms_and_focal_roles():
    entries, _ = na.cases()
    for c in entries:
        if c["family_id"] == "Q00":
            assert c["distractor_roles"] == dict(suspect="tuven", control="visuv", neighbor="pisak", far="gitix")
        if c["variant"].startswith("value_suspect_"):
            matched = next(x for x in entries if (x["family_id"], x["world"], x["format"], x["variant"])
                == (c["family_id"], c["world"], c["format"], c["variant"].replace("suspect", "control")))
            assert sorted(str(x) for x in c["state"].values()) == sorted(str(x) for x in matched["state"].values())


def test_historical_originals_are_actually_verified_when_evidence_is_present(tmp_path):
    history = Path("artifacts/memory-probe-v1/s1-preparation-20261117T200538Z/collection-bdm5ddqa/download/stage/qualification")
    if not history.exists():
        pytest.skip("historical evidence requires restoring the committed diagnostic archive")
    manifest = na.prepare(tmp_path / "historical", historical_unit=history)
    assert manifest["provenance"]["kind"] == "hash_verified_historical_replay"


def test_freeze_and_package_guards(package):
    manifest, cases = na.verify_package(package, Path.cwd())
    assert manifest["request_ceiling"] == 280 and len(cases) == 256
    with pytest.raises(FileExistsError):
        na.prepare(package)
    (package / "cases.json").write_text("[]")
    with pytest.raises(ValueError):
        na.verify_package(package)


class OffsetTokenizer(Tokenizer):
    def convert_ids_to_tokens(self, ids):
        return [chr(i) for i in ids]

    def __call__(self, text, **kwargs):
        return dict(input_ids=self.encode(text), offset_mapping=[(i, i + 1) for i in range(len(text))])


def test_name_tokens_include_boundary_contexts_and_actual_prompt_offsets():
    evidence = na.token_evidence(na.cases()[0], OffsetTokenizer(), fake=True)
    assert evidence["evidence"] == "synthetic_fixture"
    assert evidence["names"]["tevug"]["bare"]["pieces"] == list("tevug")
    assert evidence["names"]["tuven"]["json_key"]["pieces"] == list('"tuven":')
    for fmt in ("prose", "json"):
        focal = [r for r in evidence["focal_baseline_occurrences"] if f"/{fmt}/" in r["case_id"]]
        assert sum(r["name"] == "tevug" for r in focal) == 2
        assert sum(r["name"] == "tuven" for r in focal) == 1
        assert all(len(r["ids"]) == r["span"][1] - r["span"][0] for r in focal)


def test_full_offline_run_deduplicates_only_exact_method_inputs(package, tmp_path):
    model, reference = NoGeneration(), NoGeneration()
    result = na.run(package, tmp_path / "run", loader=lambda *_: (model, reference))
    assert result["status"]["complete"] and result["status"]["model_is_fake"]
    assert model.calls == 256 and reference.calls == 24
    assert result["physical_responses"] == 280 and len(result["assessments"]) == 296
    assert all(r["correct"] for r in result["assessments"])
    assert len(result["baseline_repeats"]) == 8 and all(r["label_agrees"] for r in result["baseline_repeats"])
    assert sum(r["reused"] for r in result["assessments"]) == 16


def test_reference_disagreement_stops_and_preserves_raw_records(package, tmp_path):
    output = tmp_path / "mismatch"
    with pytest.raises(ValueError, match="reference differs"):
        na.run(package, output, loader=lambda *_: (NoGeneration(), NoGeneration(force="A")))
    result = na.report(output)
    assert not result["status"]["complete"] and result["physical_responses"] == 2
    assert not (output / "completion.json").exists()


def test_repeat_disagreement_is_an_observation_without_accuracy_gate(package, tmp_path):
    class Drifting(NoGeneration):
        def answer(self, messages):
            return "A" if self.calls > 248 else super().answer(messages)
    result = na.run(package, tmp_path / "unstable", loader=lambda *_: (Drifting(), NoGeneration()))
    assert result["status"]["complete"]
    assert any(not r["label_agrees"] for r in result["baseline_repeats"])


def test_interrupted_run_keeps_unknown_usage_and_no_success_marker(package, tmp_path):
    output = tmp_path / "partial"
    with pytest.raises(RuntimeError, match="fixture inference interruption"):
        na.run(package, output, loader=lambda *_: (NoGeneration(fail_after=1), NoGeneration()))
    result = na.report(output)
    assert not result["status"]["complete"] and result["physical_responses"] == 2
    assert result["unknown_usage_requests"] == 1


def test_deadline_before_inference(package, tmp_path):
    wall, model = [0], NoGeneration()
    def loader(*args):
        wall[0] = na.SOFT_SECONDS + 1
        return model, NoGeneration()
    with pytest.raises(TimeoutError):
        na.run(package, tmp_path / "late", loader=loader, clock=lambda: wall[0])
    assert model.calls == 0


@pytest.mark.parametrize("fault", ["wrong_destination", "missing", "duplicate", "duplicate_request", "wrong_reuse"])
def test_report_reconciles_raw_evidence_even_after_rehash(package, tmp_path, fault):
    output = tmp_path / "run"
    na.run(package, output, loader=lambda *_: (NoGeneration(), NoGeneration()))
    name = "events.jsonl" if fault == "duplicate_request" else "assessments.jsonl"
    rows = na.rd._rows(output / name)
    if fault == "wrong_destination":
        rows[0]["selected_destination"] = "invented"
    elif fault == "wrong_reuse":
        rows[0]["reused"] = True
    elif fault == "missing":
        rows.pop()
    elif fault == "duplicate":
        rows[-1] = rows[0]
    else:
        rows.append(next(r for r in rows if r["event"] == "model_request"))
    (output / name).write_text("".join(json.dumps(r) + "\n" for r in rows))
    ledger = na.rd._read(output / "completion.json")
    ledger[name] = na.mp.file_sha256(output / name)
    (output / "completion.json").write_text(json.dumps(ledger))
    with pytest.raises(ValueError):
        na.report(output)


def test_import_help_are_offline():
    code = """import sys
from game_memory import name_ablation
assert not {'torch','transformers','modal'} & set(sys.modules)
sys.argv=['name-ablation','--help'];name_ablation.main()
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0 and "prepare" in result.stdout
