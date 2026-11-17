"""Offline diagnostic checks. Synthetic outputs never establish Qwen behavior."""

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from types import ModuleType, SimpleNamespace

import pytest

from game_memory import memory_probe as mp
from game_memory import reader_diagnostic as rd
from game_memory.components import Generation, Message
from test_transformers_model import tiny_adapter


HISTORY = Path("artifacts/memory-probe-v1/s1-preparation-20261117T200538Z/"
               "collection-bdm5ddqa/download/stage/qualification")


class Tokenizer:
    chat_template = "synthetic character tokenizer, not Qwen"
    all_special_ids = [0]

    def apply_chat_template(self, messages, **kwargs):
        return json.dumps(messages) + "assistant\n"

    def encode(self, text, **kwargs):
        return [ord(c) for c in text]


def note_state(text):
    if text.startswith("{"):
        return json.loads(text)
    state = {n.lower(): v for n, v in re.findall(r"(\w+) is assigned to (\w+)\.", text)}
    state.update({n.lower(): None for n in re.findall(r"(\w+)'s assignment is revoked", text)})
    return state


class FixtureModel:
    metadata = {"is_fake": True, "implementation": "synthetic_reader_diagnostic"}

    def __init__(self, *, force=None, generated=None, fail_after=None):
        self.calls = 0
        self.force, self.generated, self.fail_after = force, generated, fail_after

    def answer(self, messages):
        user = messages[1].content
        note = user.split("Retained context:\n", 1)[1].split("\n\nCurrent query:", 1)[0]
        query = user.split("What is ", 1)[1].split("'s current", 1)[0]
        options = [line[3:] for line in user.split("destination?\n", 1)[1].splitlines()]
        return self.force or mp.LABELS[options.index(note_state(note).get(query) or mp.ABSTAIN)]

    def tick(self):
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise RuntimeError("fixture inference interruption")

    def score_choices(self, messages, *, labels):
        self.tick()
        label = self.answer(messages)
        prompt = Tokenizer().apply_chat_template([asdict(m) for m in messages])
        return Generation(label, 20, 1, 0.01, {
            "candidate_logits": [2.0 if x == label else 0.0 for x in labels],
            "label_token_ids": list(map(ord, labels)),
            "rendered_prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "scoring_evidence": "synthetic_fixture"})

    def generate(self, messages, *, purpose):
        self.tick()
        text = self.generated if self.generated is not None else self.answer(messages)
        return Generation(text, 20, 2, 0.02, {"finish_reason": "eos", "synthetic": True})


@pytest.fixture
def package(tmp_path):
    path = tmp_path / "package"
    rd.prepare(path)
    return path


def test_case_selection_and_factual_content_are_fixed_and_format_matched():
    entries, provenance = rd.cases()
    assert len(entries) == 112 and len({e["prompt_sha256"] for e in entries}) == 104
    assert provenance["kind"].startswith("reconstructed")
    assert all(e["historical_correct"] is None for e in entries)
    for fid, world in rd.SELECTION:
        chosen = [e for e in entries if (e["family_id"], e["world"]) == (fid, world)]
        assert len(chosen) == 14
        assert len({json.dumps(note_state(e["memory"]), sort_keys=True) for e in chosen}) == 1
        assert all(note_state(e["memory"])[e["query"]] == e["gold"] for e in chosen)
        for variant in {e["variant"] for e in chosen} - {"original"}:
            prose, structured = [e for e in chosen if e["variant"] == variant]
            assert prose["entity_order"] == structured["entity_order"]
            assert list(json.loads(structured["memory"])) == structured["entity_order"]


def test_original_prompts_are_exact_v1_and_sibling_inputs_outside_memory_match():
    entries, _ = rd.cases()
    for family in mp.generate_splits()["qualification"]:
        for expected in mp.qualification_reads(family):
            matches = [e for e in entries if e["family_id"] == family["family_id"]
                       and e["world"] == expected["world"] and e["variant"] == "original"
                       and expected["condition"] == f"sufficient_{e['format']}"]
            for case in matches:
                assert case["messages"] == [asdict(m) for m in mp.reader_messages(
                    expected["memory"], expected["query"], family["options"])]
    for fmt in mp.FORMATS:
        for variant in {e["variant"] for e in entries}:
            siblings = [e for e in entries if e["family_id"] == "Q00"
                        and e["format"] == fmt and e["variant"] == variant]
            assert len({mp.outside_memory(e["messages"]) for e in siblings}) == 1


def test_each_intervention_changes_only_the_declared_order():
    entries, _ = rd.cases()
    for fmt in mp.FORMATS:
        chosen = {e["variant"]: e for e in entries
                  if e["family_id"] == "Q00" and e["world"] == 0 and e["format"] == fmt}
        lexical = chosen["matched_lexical"]
        assert chosen["matched_reverse"]["options"] == lexical["options"]
        assert chosen["matched_reverse"]["entity_order"] == lexical["entity_order"][::-1]
        rotated = [lexical, *(chosen[f"options_rotate_{i}"] for i in range(1, 5))]
        assert {e["options"].index("green") for e in rotated} == set(range(5))
        assert all(e["memory"] == lexical["memory"] for e in rotated)
        assert all(e["messages"][0] == lexical["messages"][0] for e in chosen.values())


def test_available_historical_evidence_is_hash_verified_and_controls_are_observed_correct():
    if not HISTORY.exists():
        pytest.skip("original Git-ignored S1 evidence unavailable; reconstruction tests still run")
    entries, provenance = rd.cases(HISTORY)
    assert provenance["kind"] == "hash_verified_historical_replay"
    originals = [e for e in entries if e["variant"] == "original"]
    assert all(e["historical_correct"] for e in originals if e["family_id"] != "Q00")
    assert sum(not e["historical_correct"] for e in originals) == 3


def test_missing_or_modified_explicit_history_does_not_fall_back_to_reconstruction(tmp_path):
    with pytest.raises(FileNotFoundError):
        rd.cases(tmp_path)
    (tmp_path / "events.jsonl").write_text("changed evidence")
    with pytest.raises(ValueError, match="historical evidence hash"):
        rd.cases(tmp_path)


@pytest.mark.parametrize("text,expected", [("A", "A"), (" E.\n", "E"), ("B\n", "B"),
    ("D. green", None), ("Answer: D", None), ("blue", None), ("a", None),
    ("A or B", None), ("", None), ("I cannot answer", None)])
def test_generated_extraction_never_guesses_a_letter_from_explanations(text, expected):
    assert rd.parse_generated(text) == expected


def test_reference_tokenization_and_ties_are_independent_and_reject_bad_encodings():
    prompt, prefix, ids = rd.reference_tokens(Tokenizer(), (Message("user", "choose"),))
    assert prefix == list(map(ord, prompt)) and ids == list(map(ord, mp.LABELS))
    assert rd.reference_argmax([0, 2, 2, 1, 0]) == "B"
    for values in ([0, 1], [0, 1, float("nan"), 3, 4], [float("inf")] * 5):
        with pytest.raises(ValueError, match="finite"):
            rd.reference_argmax(values)
    special = Tokenizer()
    special.all_special_ids = [ord("A")]
    with pytest.raises(ValueError, match="encoding"):
        rd.reference_tokens(special, (Message("user", "choose"),))


@pytest.mark.parametrize("change", ["logits", "label_ids", "prompt", "selected", "length"])
def test_reference_comparison_catches_mapping_logits_and_selection_errors(change):
    left = FixtureModel().score_choices(
        tuple(Message(**m) for m in rd.cases()[0][0]["messages"]), labels=mp.LABELS)
    metadata = dict(left.metadata)
    text, length = left.text, left.input_tokens
    if change == "logits":
        metadata["candidate_logits"] = [x + 1 for x in metadata["candidate_logits"]]
    elif change == "label_ids":
        metadata["label_token_ids"] = list(reversed(metadata["label_token_ids"]))
    elif change == "prompt":
        metadata["rendered_prompt_sha256"] = "different"
    elif change == "selected":
        text = "A" if text != "A" else "B"
    else:
        length += 1
    right = Generation(text, length, 1, 0.01, metadata)
    assert not rd.compare_scores(left, right)


def test_actual_random_weight_reference_matches_production_without_pretrained_assets(tiny_adapter):
    messages = (Message("user", "choose"),)
    production = tiny_adapter.score_choices(messages, labels=mp.LABELS)
    reference = rd.ReferenceModel(tiny_adapter).score_choices(messages, labels=mp.LABELS)
    assert rd.compare_scores(production, reference)
    assert reference.metadata["full_vocab_argmax_id"] >= 0


def test_synthetic_preflight_is_not_claimed_as_actual_tokenizer_evidence():
    checked = rd.preflight(rd.cases()[0], Tokenizer(), 1000)
    assert checked["evidence"] == "scripted_tokenizer_fixture"
    assert len(checked["prompts"]) == 104


def test_package_and_ceiling_are_immutable_and_reconstruction_is_explicit(package):
    manifest, entries = rd.verify_package(package, source=Path.cwd())
    assert manifest["request_ceiling"] == 312 and manifest["max_generated_tokens"] == 3328
    assert manifest["provenance"]["kind"].startswith("reconstructed")
    assert len(entries) == 112
    with pytest.raises(FileExistsError):
        rd.prepare(package)
    data = json.loads((package / "cases.json").read_text())
    data[0]["gold"] = "invented"
    (package / "cases.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="package hash"):
        rd.verify_package(package)
    manifest["files"]["cases.json"] = mp.file_sha256(package / "cases.json")
    manifest["manifest_sha256"] = mp.digest({k: v for k, v in manifest.items() if k != "manifest_sha256"})
    (package / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="prespecified"):
        rd.verify_package(package)


@pytest.fixture
def completed(package, tmp_path):
    directory = tmp_path / "run"
    rd.run(package, directory, loader=lambda *_: (FixtureModel(), FixtureModel()))
    return directory


def test_complete_fixture_reuses_only_identical_prompts_and_reconciles_usage(completed):
    result = rd.report(completed)
    assert result["status"]["complete"] and result["status"]["model_is_fake"]
    assert len(result["assessments"]) == 336 and result["physical_responses"] == 312
    assert sum(r["reused"] for r in result["assessments"]) == 24
    assert result["known_input_tokens"] == 312 * 20
    assert result["known_output_tokens"] == 208 + 104 * 2
    assert all(r["correct"] for r in result["assessments"])
    assert all(r["option_mapping"][r["selected_letter"]] == r["selected_destination"]
               for r in result["assessments"])


def test_unparseable_generation_is_retained_and_counts_as_wrong(package, tmp_path):
    result = rd.run(package, tmp_path / "run", loader=lambda *_: (
        FixtureModel(generated="D. green"), FixtureModel()))
    generated = [r for r in result["assessments"] if r["method"] == "generated"]
    assert all(r["unparseable"] and not r["correct"] and r["raw_answer"] == "D. green"
               for r in generated)


def test_diagnostic_generation_crosses_the_real_backend_purpose_contract_offline(package, tmp_path, monkeypatch):
    from game_memory.transformers_model import TransformersConfig, TransformersModel

    class ReachedTokenizer(Exception):
        pass

    def stop_before_tensor_work(*args, **kwargs):
        raise ReachedTokenizer

    # Exercise the actual adapter's validation branch without loading optional
    # libraries, constructing weights, or performing a forward/generation.
    monkeypatch.setitem(sys.modules, "torch", ModuleType("torch"))
    transformers = ModuleType("transformers")
    transformers.GenerationConfig = object
    monkeypatch.setitem(sys.modules, "transformers", transformers)
    adapter = object.__new__(TransformersModel)
    adapter.config = TransformersConfig(revision=mp.MODEL_REVISION, action_max_new_tokens=32)
    adapter._tokenizer = SimpleNamespace(apply_chat_template=stop_before_tensor_work)

    class ContractModel(FixtureModel):
        def generate(self, messages, *, purpose):
            try:
                TransformersModel.generate(adapter, messages, purpose=purpose)
            except ReachedTokenizer:
                return super().generate(messages, purpose=purpose)
            pytest.fail("backend did not reach the tokenizer boundary")

    result = rd.run(package, tmp_path / "backend-contract", loader=lambda *_: (
        ContractModel(), FixtureModel()))
    assert result["status"]["complete"] and result["physical_responses"] == 312


def test_scoring_disagreement_stops_before_generation_and_preserves_raw_evidence(package, tmp_path):
    model = FixtureModel()
    output = tmp_path / "mismatch"
    with pytest.raises(ValueError, match="scoring disagreement"):
        rd.run(package, output, loader=lambda *_: (model, FixtureModel(force="A")))
    result = rd.report(output)
    assert not result["status"]["complete"] and result["physical_responses"] == 2
    assert model.calls == 1 and not (output / "completion.json").exists()
    assert "scoring_mismatch" in (output / "events.jsonl").read_text()


def test_interrupted_request_keeps_error_and_known_usage_and_refuses_overwrite(package, tmp_path):
    output = tmp_path / "interrupted"
    with pytest.raises(RuntimeError, match="fixture inference interruption"):
        rd.run(package, output, loader=lambda *_: (FixtureModel(fail_after=2), FixtureModel()))
    result = rd.report(output)
    assert result["status"]["attempted_requests"] == 4
    assert result["physical_responses"] == 3 and not result["status"]["usage_complete"]
    assert len(result["assessments"]) == 3
    assert "model_error" in (output / "events.jsonl").read_text()
    with pytest.raises(FileExistsError):
        rd.run(package, output, loader=lambda *_: pytest.fail("existing output reached loader"))


def test_generation_failure_keeps_the_two_already_completed_reader_decisions(package, tmp_path):
    output = tmp_path / "generation-failure"
    with pytest.raises(RuntimeError, match="fixture inference interruption"):
        rd.run(package, output, loader=lambda *_: (FixtureModel(fail_after=1), FixtureModel()))
    result = rd.report(output)
    assert not result["status"]["complete"] and result["physical_responses"] == 2
    assert [r["method"] for r in result["assessments"]] == ["restricted", "reference"]


def test_load_failure_and_deadline_before_first_request_are_visible(package, tmp_path):
    def broken(*_):
        raise OSError("fixture weight-load failure")
    with pytest.raises(OSError, match="weight-load failure"):
        rd.run(package, tmp_path / "load", loader=broken)
    assert rd.report(tmp_path / "load")["status"]["attempted_requests"] == 0
    wall = [0]
    def late(*_):
        wall[0] = rd.SOFT_SECONDS
        return FixtureModel(), FixtureModel()
    with pytest.raises(TimeoutError):
        rd.run(package, tmp_path / "deadline", loader=late, clock=lambda: wall[0])
    assert rd.report(tmp_path / "deadline")["physical_responses"] == 0


def test_status_save_failure_does_not_replace_the_original_inference_error(package, tmp_path, monkeypatch):
    save = rd.transport.save
    def fail_status(path, value):
        if path.name == "status.json":
            raise OSError("fixture disk failure")
        return save(path, value)
    monkeypatch.setattr(rd.transport, "save", fail_status)
    with pytest.raises(RuntimeError, match="fixture inference interruption") as raised:
        rd.run(package, tmp_path / "run", loader=lambda *_: (
            FixtureModel(fail_after=0), FixtureModel()))
    assert "fixture disk failure" in str(raised.value.__notes__)


@pytest.mark.parametrize("fault", ["wrong_destination", "missing_row", "duplicate_row"])
def test_report_recomputes_decisions_and_coverage_even_if_completion_is_rehashed(completed, fault):
    path = completed / "assessments.jsonl"
    rows = [json.loads(s) for s in path.read_text().splitlines()]
    if fault == "wrong_destination":
        rows[0]["selected_destination"] = "invented"
    elif fault == "missing_row":
        rows.pop()
    else:
        rows[-1] = rows[0]
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    ledger = json.loads((completed / "completion.json").read_text())
    ledger[path.name] = mp.file_sha256(path)
    (completed / "completion.json").write_text(json.dumps(ledger))
    with pytest.raises(ValueError, match="assessment|coverage"):
        rd.report(completed)


def test_import_help_and_missing_authorization_never_import_inference_packages():
    code = """import sys
from game_memory import reader_diagnostic as rd
assert 'torch' not in sys.modules and 'transformers' not in sys.modules
sys.argv=['reader-diagnostic','--help']
rd.main()
"""
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=15)
    assert done.returncode == 0 and "prepare" in done.stdout
    done = subprocess.run([sys.executable, "-c", code.replace("'--help'", "'run'")],
                          capture_output=True, text=True, timeout=15)
    assert done.returncode != 0 and "--authorization" in done.stderr


def test_authorization_template_is_rejected_before_loading_models(package, tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["diagnostic", "run", "--package", str(package),
        "--output-dir", str(tmp_path / "run"), "--authorization", str(package / "authorization-template.txt")])
    monkeypatch.setattr(rd, "load_models", lambda *_: pytest.fail("template reached inference boundary"))
    with pytest.raises(SystemExit) as raised:
        rd.main()
    assert raised.value.code == 2 and not (tmp_path / "run").exists()
