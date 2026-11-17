"""memory-probe-v1 tests. All models and tokenizers here are synthetic fixtures."""

from dataclasses import asdict
import copy
import json
from pathlib import Path
import re

import pytest

from game_memory import memory_probe as mp
from game_memory.components import Generation, MemoryContext
from game_memory.memory import ProseMemory, StructuredMemory


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def splits():
    return mp.generate_splits()


# ------------------------------------------------------------- synthetic fixture model

def _parse_memory(text):
    """Fixture-only reading of the fixture's own notes (not a model of Qwen)."""
    text = text.strip()
    if not text:
        return {}
    if text.startswith("["):
        return mp.public_state([r["observation"] for r in json.loads(text)])["state"]
    if text.startswith("{"):
        return json.loads(text)
    state = {}
    for name, value in re.findall(r"(\w+) is assigned to (\w+)\.", text):
        state[name.lower()] = value
    for name in re.findall(r"(\w+)'s assignment is revoked", text):
        state[name.lower()] = None
    return state


class FixtureModel:
    """Synthetic writer/reader. writer(previous_state, observation, fmt) may be overridden."""

    def __init__(self, *, writer=None, reader=None, fail_after=None):
        self.writer = writer
        self.reader = reader
        self.calls = 0
        self.fail_after = fail_after

    @property
    def metadata(self):
        return {"implementation": "FixtureModel", "is_fake": True}

    def count_tokens(self, text):
        return len(text) // 4  # synthetic counter, not Qwen tokenization

    def _tick(self):
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise RuntimeError("synthetic transport failure")

    def generate(self, messages, *, purpose):
        self._tick()
        payload = json.loads(messages[1].content)
        fmt = "json" if "JSON object" in messages[0].content else "prose"
        if self.writer is not None:
            return Generation(self.writer(payload, fmt, purpose), 10, 5, 0.0,
                              {"do_sample": False, "use_model_defaults": False})
        state = _parse_memory(payload["previous_memory"])
        update = mp.public_state([payload["observation"]])["state"]
        state.update(update)
        order = sorted(state)
        reduced = {"order": order, "state": state}
        text = mp.json_note(reduced) if fmt == "json" else mp.prose_note(reduced)
        return Generation(text, 10, 5, 0.0, {"do_sample": False, "use_model_defaults": False})

    def score_choices(self, messages, *, labels):
        self._tick()
        user = messages[1].content
        memory = user.split("\nRetained context:\n", 1)[1].split("\n\nCurrent query:\n", 1)[0]
        query = user.rsplit("What is ", 1)[1].split("'s current", 1)[0]
        options = [line[3:] for line in user.rsplit("destination?\n", 1)[1].split("\n")]
        if self.reader is not None:
            answer = self.reader(memory, query, options)
        else:
            answer = _parse_memory(memory).get(query) or mp.ABSTAIN
        label = labels[options.index(answer)]
        logits = [1.0 if x == label else 0.0 for x in labels]
        return Generation(label, 20, 1, 0.0, {"labels": list(labels), "candidate_logits": logits,
                                              "selected_label": label, "scoring_evidence": "fixture"})


def commit_log():
    log = []
    return log, lambda: log.append("commit")


# ------------------------------------------------------------- v17 preservation

def test_v17_default_writer_messages_are_byte_identical_to_pre_refactor_capture():
    cases = json.loads((FIXTURES / "v17-writer-messages.json").read_text())
    for case in cases:
        memory = ProseMemory() if case["strategy"] == "prose" else StructuredMemory()
        calls = []

        class Capture:
            metadata = {"is_fake": True}
            outputs = iter(case["outputs"])

            def count_tokens(self, text):
                return len(text)

            def generate(self, messages, *, purpose):
                calls.append({"purpose": purpose, "messages": [asdict(m) for m in messages]})
                return Generation(next(self.outputs), 1, 1, 0.0)

        memory.update(case["previous"], case["action"], case["observation"],
                      MemoryContext(**case["context"]), Capture())
        assert calls == case["calls"], (case["strategy"], case["case"])
    assert {c["case"] for c in cases} == {"initialization", "update", "repair"}


# ------------------------------------------------------------- generator

def test_quartets_cover_answers_and_share_reader_inputs_outside_memory(splits):
    for families in splits.values():
        for f in families:
            assert [w["answer"] for w in f["worlds"]] == list(mp.DESTINATIONS)
            outside = {mp.outside_memory([asdict(m) for m in mp.reader_messages(
                mp.json_note(mp.public_state(w["observations"])), f["roles"]["target"], f["options"])])
                for w in f["worlds"]}
            assert len(outside) == 1


def test_updated_query_quartets_have_no_old_to_new_rule(splits):
    olds = {}
    for split, families in splits.items():
        for f in (x for x in families if x["query_type"] == "updated"):
            target = f["roles"]["target"]
            assert f["roles"]["updated"] == target
            assert len({w["observations"][0] for w in f["worlds"]}) == 1
            old = f["worlds"][0]["initial"][target]
            # The same old value maps to every new value, including itself.
            assert sorted(w["update_value"] for w in f["worlds"]) == sorted(mp.DESTINATIONS)
            assert old in [w["update_value"] for w in f["worlds"]]
            assert all(mp.public_state(w["observations"])["state"][target] == w["answer"]
                       for w in f["worlds"])
            olds.setdefault(split, []).append(old)
    assert len(set(olds["test"])) == 4 and len(set(olds["qualification"])) == 2


def test_untouched_query_siblings_share_update_and_vary_target(splits):
    for f in (x for fs in splits.values() for x in fs if x["query_type"] == "untouched"):
        r = f["roles"]
        assert r["updated"] != r["target"] != r["revoked"] != r["updated"]
        assert len({w["observations"][1] for w in f["worlds"]}) == 1
        assert [w["initial"][r["target"]] for w in f["worlds"]] == list(mp.DESTINATIONS)


def test_generation_is_deterministic_and_seeded_by_sha256(splits):
    assert mp.digest(mp.generate_splits()) == mp.digest(splits)
    assert mp.stream("test", 0, "x").random() == mp.stream("test", 0, "x").random()
    assert mp.stream("test", 0, "x").random() != mp.stream("test", 1, "x").random()


def _clone(splits):
    return copy.deepcopy(splits)


@pytest.mark.parametrize("mutation,message", [
    (lambda s: s["test"][0]["order"].__setitem__(0, "green"), "invalid entity names"),
    (lambda s: s["test"][1]["roles"].__setitem__("revoked", s["test"][1]["roles"]["target"]),
     "revoked entity overlaps"),
    (lambda s: [w["observations"].__setitem__(2, f"Ambient pulse {s['test'][0]['order'][3]}. "
                                              "No assignments changed.") for w in s["test"][0]["worlds"]],
     "filler contains a fact"),
    (lambda s: s["test"][0]["pulses"].__setitem__(0, s["dev"][0]["order"][0]), "shared across splits"),
    (lambda s: s["test"].__setitem__(0, s["dev"][0] | {"family_id": "T00", "split": "test"}),
     "shared across splits"),
])
def test_split_checks_reject_collisions_and_leaks(splits, mutation, message):
    broken = _clone(splits)
    mutation(broken)
    with pytest.raises(ValueError, match=message):
        mp.check_splits(broken)


def test_shared_normalized_composition_is_rejected(splits):
    broken = _clone(splits)
    donor = broken["dev"][0]
    clone = copy.deepcopy(donor)
    renames = {n: f"zz{chr(97 + i)}az" for i, n in enumerate(donor["order"])}

    def rn(text):
        for old, new in renames.items():
            text = text.replace(old, new).replace(old.capitalize(), new.capitalize())
        return text
    clone["order"] = [renames[n] for n in donor["order"]]
    clone["base"] = {renames[n]: v for n, v in donor["base"].items()}
    clone["roles"] = {k: renames[v] for k, v in donor["roles"].items()}
    clone["pulses"] = [f"qq{chr(97 + i)}iz" for i in range(12)]
    for w in clone["worlds"]:
        w["initial"] = {renames[n]: v for n, v in w["initial"].items()}
        w["observations"] = [rn(o) for o in w["observations"][:2]] + [
            f"Ambient pulse {p}. No assignments changed." for p in clone["pulses"]]
    clone["family_id"], clone["split"] = "T00", "test"
    broken["test"][0] = clone
    with pytest.raises(ValueError, match="normalized composition"):
        mp.check_splits(broken)


# ------------------------------------------------------------- writer boundary

def test_probe_writer_payload_whitelist_and_identity():
    messages = mp.writer_messages("json", "{}", mp.INITIAL, "Assignments: a=b.", 64)
    payload = json.loads(messages[1].content)
    assert set(payload) == mp.WRITER_FIELDS
    assert payload["public_rules"] == mp.PUBLIC_RULES and payload["memory_token_limit"] == 64
    assert "budget_remaining" not in messages[1].content and "recheck_cost" not in messages[1].content
    assert messages[0].content.startswith("Memory writer probe-writer-v1\n" + mp.WRITER_INSTRUCTION)
    assert messages[0].content.endswith(StructuredMemory.format_instructions)
    for cls in (mp.ProbeProseMemory, mp.ProbeStructuredMemory):
        meta = cls().metadata
        assert meta["prompt_version"] == "probe-writer-v1" and "version" not in meta
    with pytest.raises(ValueError, match="marker"):
        mp.writer_messages("prose", "", "take cheese", "x", 64)


def test_writer_requests_are_invariant_to_future_query_options_and_gold(splits, tmp_path):
    family = splits["test"][0]
    altered = copy.deepcopy(family)
    altered["roles"]["target"] = family["order"][5]
    altered["options"] = list(reversed(family["options"]))
    for w in altered["worlds"]:
        w["answer"] = mp.ABSTAIN
    requests = []
    for name, fam in (("a", family), ("b", altered)):
        unit = mp._Unit(tmp_path / name, FixtureModel(), float("inf"), lambda: 0.0)
        unit.chain(fam, fam["worlds"][2], "prose", 256)
        unit.close()
        requests.append([e["messages"] for e in mp._jsonl(tmp_path / name / "events.jsonl")
                         if e["event"] == "model_request"])
    assert requests[0] == requests[1] and len(requests[0]) == 14


def test_probe_writer_inherits_repair_and_exact_previous_state_fallback():
    context = mp.ProbeContext(mp.PUBLIC_RULES, 8)

    class Scripted:
        metadata = {"is_fake": True}

        def __init__(self, outputs):
            self.outputs = iter(outputs)
            self.purposes = []

        def count_tokens(self, text):
            return len(text) // 4

        def generate(self, messages, *, purpose):
            self.purposes.append(purpose)
            return Generation(next(self.outputs), 1, 1, 0.0)

    writer = mp.ProbeStructuredMemory()
    model = Scripted(['{"a":1,"a":2}', '{"a":"blue"}'])
    result = writer.update("{}", mp.INITIAL, "obs", context, model)
    assert result.memory == '{"a":"blue"}' and model.purposes == ["memory", "memory_repair"]
    model = Scripted(['{"a":NaN}', "x" * 80])
    result = writer.update('{"k":"v"}', mp.UPDATE, "obs", context, model)
    assert result.memory == '{"k":"v"}' and result.events[-1] == "memory_fallback:previous_valid_memory"


# ------------------------------------------------------------- reader

def test_reader_input_has_no_probe_position_and_options_are_family_level(splits):
    f = splits["test"][3]
    messages = mp.reader_messages("note", f["roles"]["target"], f["options"])
    text = messages[0].content + messages[1].content
    assert not any(token in text for token in ("P0", "P12", "256", "64", f["family_id"]))
    assert messages == mp.reader_messages("note", f["roles"]["target"], f["options"])
    assert all("options" not in w for w in f["worlds"])


# ------------------------------------------------------------- replay, reuse, counts

@pytest.fixture(scope="module")
def family_run(splits, tmp_path_factory):
    directory = tmp_path_factory.mktemp("family") / "T00"
    log, commit = commit_log()
    record = mp.run_family(splits["test"][0], (64, 256), directory, FixtureModel(), commit=commit)
    return directory, record, log


def test_family_replay_counts_audit_and_probe_isolation(splits, family_run):
    directory, record, log = family_run
    audit = mp.audit_family(directory, splits["test"][0], real=False, allowances=(64, 256))
    assert audit["writes"] == 224 and audit["primary"] == 32 and audit["reference"] == 32
    assert audit["carry_forward"] == 16 and audit["reader_calls"] <= 49 and log == ["commit"]
    writer_inputs = [e for e in mp._jsonl(directory / "events.jsonl")
                     if e["event"] == "model_request" and e["purpose"].startswith("memory")]
    assert all("Current query" not in json.dumps(e["messages"]) for e in writer_inputs)
    rows = mp._jsonl(directory / "assessments.jsonl")
    for cf in (r for r in rows if r["kind"] == "carry_forward"):
        p0 = next(r for r in rows if r["kind"] == "primary" and r["probe"] == "P0"
                  and all(r[k] == cf[k] for k in ("world", "format", "allowance")))
        assert cf["source_request_id"] == p0["source_request_id"]
    refs = [r for r in rows if r["kind"] == "reference"]
    assert len({r["source_request_id"] for r in refs}) == 17


def test_reuse_is_exact_identity_and_scores_each_assessment_with_its_own_gold(splits, tmp_path):
    log, commit = commit_log()
    mp.run_qualification(splits["qualification"], tmp_path / "q", FixtureModel(), commit=commit)
    rows = mp._jsonl(tmp_path / "q" / "assessments.jsonl")
    assert len(rows) == 96
    assert len({(r["family_id"], r["source_request_id"]) for r in rows}) == 76
    no_memory = [r for r in rows if r["condition"] == "no_memory" and r["family_id"] == "Q00"]
    assert len({r["source_request_id"] for r in no_memory}) == 1
    assert sorted(r["gold"] for r in no_memory) == sorted(mp.DESTINATIONS)
    assert all(r["correct"] == (r["chosen"] == r["gold"]) for r in rows)
    for r in rows:
        if r["reused"]:
            source = next(x for x in rows if x["source_request_id"] == r["source_request_id"]
                          and not x["reused"])
            assert source["prompt_sha256"] == r["prompt_sha256"]
    gate = mp.qualification_gate(tmp_path / "q", splits["qualification"])
    assert gate["passed"] and gate["distinct_prompts"] == 76 and gate["logical_assessments"] == 96


def test_qualification_gate_fails_when_reader_cannot_use_context(splits, tmp_path):
    log, commit = commit_log()
    always_abstain = FixtureModel(reader=lambda memory, query, options: mp.ABSTAIN)
    mp.run_qualification(splits["qualification"], tmp_path / "q", always_abstain, commit=commit)
    gate = mp.qualification_gate(tmp_path / "q", splits["qualification"])
    assert not gate["passed"] and not gate["checks"]["full_history"]
    assert gate["checks"]["missing_prose"] and gate["checks"]["no_memory_at_most_4"]


# ------------------------------------------------------------- gates

def _rows(prose_high, prose_low, json_high, json_low, low=64):
    rows = []
    for fmt, b, correct in (("prose", 256, prose_high), ("prose", low, prose_low),
                            ("json", 256, json_high), ("json", low, json_low)):
        rows += [{"kind": "primary", "probe": "P12", "format": fmt, "allowance": b,
                  "correct": i < correct} for i in range(8)]
    return rows


def test_pilot_rule_allows_crossover_and_applies_floor_and_stop():
    crossover = mp.pilot_rule(_rows(6, 4, 6, 8))  # prose 75->50, JSON 75->100
    assert crossover == {"stop": False, "p12_high_correct": {"prose": 6, "json": 6},
                         "p12_low64_pooled": 12, "low": 64}
    assert mp.pilot_rule(_rows(6, 1, 6, 2))["low"] == 128
    assert mp.pilot_rule(_rows(2, 8, 1, 8)) | {} == {"stop": True, "p12_high_correct":
                                                     {"prose": 2, "json": 1},
                                                     "p12_low64_pooled": 16, "low": None}
    assert mp.pilot_rule(_rows(3, 0, 0, 4))["low"] == 64  # one format above the stop threshold


def test_incomplete_pilot_produces_no_decision(splits, family_run, tmp_path):
    directory, _, _ = family_run
    decision = mp.pilot_decision([tmp_path / "missing", directory], splits["dev"])
    assert decision["complete"] is False and decision["low"] is None


# ------------------------------------------------------------- durability and failures

def test_each_family_is_complete_and_committed_before_the_next_starts(splits, tmp_path):
    package = _package(tmp_path, splits)
    order = []
    out = tmp_path / "s2"

    def commit():
        done = sorted(p.name for p in out.glob("T*") if (p / "completion.json").exists())
        started = sorted(p.name for p in out.glob("T*"))
        for name in done:
            mp.verify_completion(out / name)
        order.append((done, started))

    status = mp.run_stage("s2", package, out, FixtureModel(), commit=commit, low=64,
                          families=["T00", "T01"])
    assert status["outcome"] == "families_complete" and status["model_is_fake"]
    assert order[0] == (["T00"], ["T00"]) and order[1] == (["T00", "T01"], ["T00", "T01"])
    assert (out / "stage-status.json").exists()


def test_interrupted_family_has_no_completion_and_stage_records_error(splits, tmp_path):
    package = _package(tmp_path, splits)
    log, commit = commit_log()
    out = tmp_path / "s2"
    with pytest.raises(RuntimeError, match="synthetic transport failure"):
        mp.run_stage("s2", package, out, FixtureModel(fail_after=30), commit=commit, low=64,
                     families=["T00"])
    assert not (out / "T00" / "completion.json").exists()
    with pytest.raises(mp.AuditError, match="no completion record"):
        mp.verify_completion(out / "T00")
    status = json.loads((out / "stage-status.json").read_text())
    assert status["outcome"] == "error" and log == ["commit"]
    events = mp._jsonl(out / "T00" / "events.jsonl")
    assert events[-1]["event"] == "model_error"


def test_soft_deadline_stops_before_a_request_and_is_recorded(splits, tmp_path):
    package = _package(tmp_path, splits)
    log, commit = commit_log()
    out = tmp_path / "s2"
    ticks = iter(range(10_000))
    with pytest.raises(mp.StageTimeout):
        mp.run_stage("s2", package, out, FixtureModel(), commit=commit, low=64, families=["T00"],
                     deadline=5, clock=lambda: next(ticks))
    assert json.loads((out / "stage-status.json").read_text())["outcome"] == "timeout"
    assert not (out / "T00" / "completion.json").exists()


def test_s2_requires_an_s1_selected_low_allowance(splits, tmp_path):
    with pytest.raises(ValueError, match="B_low"):
        mp.run_stage("s2", _package(tmp_path, splits), tmp_path / "o", FixtureModel(),
                     commit=lambda: None, low=96)


# ------------------------------------------------------------- auditor negatives

def _copy_unit(src, dst):
    dst.mkdir()
    for p in src.iterdir():
        (dst / p.name).write_bytes(p.read_bytes())
    return dst


def _rewrite(directory, name, transform):
    path = directory / name
    rows = mp._jsonl(path)
    rows = transform(rows)
    path.write_text("".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in rows))
    record = json.loads((directory / "completion.json").read_text())
    record["files"][name] = mp.file_sha256(path)
    (directory / "completion.json").write_text(json.dumps(record))


def _first(rows, predicate, change):
    for r in rows:
        if predicate(r):
            change(r)
            break
    return rows


def _flip_logits(r):
    logits = r["metadata"]["candidate_logits"]
    r["metadata"]["candidate_logits"] = logits[1:] + logits[:1]


TAMPERING = {
    "logits": ("events.jsonl", lambda r: r["event"] == "model_response" and r["purpose"] == "action",
               _flip_logits, "selected label"),
    "label": ("assessments.jsonl", lambda r: r["kind"] == "primary",
              lambda r: r.update(selected_label="E" if r["selected_label"] != "E" else "A"), "selected label"),
    "accepted_memory": ("writes.jsonl", lambda r: r["write_index"] == 1,
                        lambda r: r.update(state=r["state"] + " Extra.", rendered=r["rendered"] + " Extra."),
                        "stored memory differs"),
    "previous_memory": ("writes.jsonl", lambda r: r["write_index"] == 5,
                        lambda r: r.update(previous_state="tampered"), "previous state"),
    "writer_request": ("events.jsonl", lambda r: r["event"] == "model_request" and r["purpose"] == "memory",
                       lambda r: r["messages"][1].update(content=r["messages"][1]["content"].replace(
                           "Assignments", "Assignmentz")), "frozen protocol"),
}


@pytest.mark.parametrize("name", sorted(TAMPERING))
def test_auditor_rejects_tampered_links(splits, family_run, tmp_path, name):
    directory, _, _ = family_run
    unit = _copy_unit(directory, tmp_path / "T00")
    file, predicate, change, message = TAMPERING[name]
    _rewrite(unit, file, lambda rows: _first(rows, predicate, change))
    with pytest.raises(mp.AuditError, match=message):
        mp.audit_family(unit, splits["test"][0], real=False, allowances=(64, 256))


def test_auditor_rejects_changed_option_order(splits, family_run):
    directory, _, _ = family_run
    family = copy.deepcopy(splits["test"][0])
    family["options"] = family["options"][1:] + family["options"][:1]
    with pytest.raises(mp.AuditError):
        mp.audit_family(directory, family, real=False, allowances=(64, 256))


def test_auditor_rejects_fixture_evidence_claimed_as_real(splits, family_run):
    directory, _, _ = family_run
    with pytest.raises(mp.AuditError, match="actual model forward"):
        mp.audit_family(directory, splits["test"][0], real=True, allowances=(64, 256))


def test_auditor_rejects_missing_file_or_hash_mismatch(family_run, tmp_path, splits):
    directory, _, _ = family_run
    unit = _copy_unit(directory, tmp_path / "a")
    (unit / "writes.jsonl").unlink()
    with pytest.raises(mp.AuditError, match="missing writes.jsonl"):
        mp.audit_family(unit, splits["test"][0], real=False, allowances=(64, 256))
    unit = _copy_unit(directory, tmp_path / "b")
    (unit / "assessments.jsonl").write_text("{}\n")
    with pytest.raises(mp.AuditError, match="hash mismatch"):
        mp.audit_family(unit, splits["test"][0], real=False, allowances=(64, 256))


@pytest.mark.parametrize("raw", ['{"a":"blue","a":"green"}', '{"a":NaN}', '{"a":1e999}',
                                 '{"a":0.1000000000000000055511151231257827}',
                                 '{"a":"' + "x" * 2000 + '"}'])  # last: valid but over budget
def test_auditor_rejects_falsely_accepted_invalid_json(splits, tmp_path, raw):
    """A writer record claiming acceptance of strict-policy-invalid JSON must fail audit."""
    family = splits["test"][0]
    outputs = iter([raw, '{"a":"blue"}'])

    def writer(payload, fmt, purpose):
        if payload["last_event"] == mp.INITIAL and purpose in {"memory", "memory_repair"}:
            return next(outputs, '{"a":"blue"}')
        return payload["previous_memory"]

    unit_dir = tmp_path / "u"
    unit = mp._Unit(unit_dir, FixtureModel(writer=writer), float("inf"), lambda: 0.0)
    unit.chain(family, family["worlds"][0], "json", 256)
    unit.complete({}, lambda: None)
    mp.audit_unit(unit_dir, [family], real=False)  # honest record: rejected, then repaired

    def falsify(rows):
        first = rows[0]
        first["request_ids"] = first["request_ids"][:1]
        first["update_events"] = ["memory_accepted"]
        return rows
    _rewrite(unit_dir, "writes.jsonl", falsify)
    with pytest.raises(mp.AuditError, match="rejected candidate without a repair"):
        mp.audit_unit(unit_dir, [family], real=False)


# ------------------------------------------------------------- analysis and annotation

def test_family_interaction_hand_computed():
    rows = []
    for fmt, b, correct in (("json", 64, 4), ("prose", 64, 2), ("json", 256, 3), ("prose", 256, 3)):
        rows += [{"kind": "primary", "probe": "P12", "format": fmt, "allowance": b,
                  "correct": i < correct} for i in range(4)]
    assert mp.family_interaction(rows, 64) == pytest.approx(0.5)
    with pytest.raises(mp.AuditError):
        mp.family_interaction(rows[:-1], 64)


def test_bootstrap_is_reproducible_and_labelled_descriptive():
    a = mp.bootstrap([0.0, 0.25, -0.25, 0.5], [0.0, 0.0, 0.25, -0.5])
    assert a == mp.bootstrap([0.0, 0.25, -0.25, 0.5], [0.0, 0.0, 0.25, -0.5])
    assert a["lower_2_5"] <= a["upper_97_5"] and "coverage not established" in a["note"]


@pytest.fixture(scope="module")
def full_test_run(splits, tmp_path_factory):
    root = tmp_path_factory.mktemp("s2")
    dirs = {}
    for family in splits["test"]:
        dirs[family["family_id"]] = root / family["family_id"]
        mp.run_family(family, (64, 256), dirs[family["family_id"]], FixtureModel(), commit=lambda: None)
    return dirs


def test_analysis_requires_complete_coverage_and_reports_raw_interactions(splits, full_test_run):
    result = mp.analyze(full_test_run, splits["test"], 64, real=False)
    assert len(result["d_f"]) == 8 and sum(result["signs"].values()) == 8
    assert result["question"] == "256 versus 64 tokens"
    assert result["bootstrap"]["samples"] == 10000
    partial = dict(full_test_run)
    partial.pop("T07")
    with pytest.raises(mp.AuditError, match="all eight"):
        mp.analyze(partial, splits["test"], 64, real=False)
    with pytest.raises(mp.AuditError):
        mp.analyze(full_test_run, splits["test"], 128, real=False)  # wrong declared allowance


def test_annotation_plan_is_balanced_and_sheet_hides_outcomes(splits, full_test_run):
    plan = mp.annotation_plan(splits["test"])
    for kind in ("updated", "untouched"):
        items = [p for p in plan if p["query_type"] == kind]
        assert len(items) == 4 and sorted(p["answer"] for p in items) == sorted(mp.DESTINATIONS)
    assert plan == mp.annotation_plan(splits["test"])
    sheet = mp.annotation_sheet(plan, full_test_run, splits["test"], 64)
    assert len(sheet) == 32
    assert not any(k in row for row in sheet for k in ("correct", "chosen", "selected_label", "gold"))


# ------------------------------------------------------------- package and preflight

def _package(tmp_path, splits):
    root = Path(__file__).resolve().parents[1]
    package = tmp_path / "package"
    mp.prepare(package, root, parent_commit="test")
    return package


def test_package_freezes_splits_counts_and_source_hashes(splits, tmp_path):
    package = _package(tmp_path, splits)
    manifest = json.loads((package / "manifest.json").read_text())
    assert manifest["planned"]["qualification_distinct_prompts"] == 76
    assert manifest["planned"]["per_family"]["reference_physical_by_test_family"] == [17] * 8
    assert mp.load_splits(package) == json.loads(json.dumps(splits))
    root = Path(__file__).resolve().parents[1]
    assert mp.verify_source(package, root)["matches"]
    with pytest.raises(FileExistsError):
        mp.prepare(package, root, parent_commit="test")
    (package / "splits" / "test.json").write_text("[]")
    with pytest.raises(mp.AuditError, match="differs from the manifest"):
        mp.load_splits(package)


def test_fixture_preflight_is_labelled_synthetic(splits, tmp_path):
    report = mp.fixture_preflight(_package(tmp_path, splits))
    assert report["evidence"] == "synthetic_fixture_not_tokenizer_evidence"
    assert report["qualification_distinct_prompts"] == 76
    assert report["actual_tokenizer_preflight"].startswith("unexecuted")


class CharTokenizer:
    """Synthetic character tokenizer for exercising preflight logic only."""

    all_special_ids = []
    chat_template = "synthetic"

    def __init__(self, scale=1):
        self.scale = scale

    def apply_chat_template(self, messages, tokenize, add_generation_prompt):
        return "".join(f"<{m['role']}>{m['content']}" for m in messages) + "<assistant>"

    def encode(self, text, add_special_tokens=False):
        return [ord(c) for c in text] * self.scale


def test_actual_preflight_logic_with_synthetic_tokenizer(splits, tmp_path):
    package = _package(tmp_path, splits)
    report = mp.actual_preflight(package, CharTokenizer(), vocab_size=0x110000)
    assert report["reader_prompts"] == 76 and report["label_token_ids"] == [65, 66, 67, 68, 69]
    assert not report["passed"]  # character counts of the notes exceed 256: preflight must stop
    assert report["evidence"] == "scripted_tokenizer_fixture"  # only the S1 worker may label it actual


# ------------------------------------------------------------- P1 revision: coverage, pilot, repair

def test_repair_instruction_matches_the_pre_refactor_v17_capture():
    cases = json.loads((FIXTURES / "v17-writer-messages.json").read_text())
    repair = next(c for c in cases if c["case"] == "repair")
    final = repair["calls"][1]["messages"][-1]
    reason = "over_budget:300>256" if repair["strategy"] == "prose" else "malformed_json"
    assert final == {"role": "user", "content": mp.REPAIR_INSTRUCTION.format(reason=reason, limit=256)}


def _swap_row(rows, predicate_target, predicate_source):
    source = next(r for r in rows if predicate_source(r))
    index = next(i for i, r in enumerate(rows) if predicate_target(r))
    rows[index] = dict(source)
    return rows


def test_family_audit_rejects_a_valid_row_duplicated_in_place_of_a_missing_one(splits, family_run, tmp_path):
    directory, _, _ = family_run
    unit = _copy_unit(directory, tmp_path / "T00")
    _rewrite(unit, "assessments.jsonl", lambda rows: _swap_row(
        rows, lambda r: r["kind"] == "primary" and r["world"] == 3 and r["probe"] == "P12",
        lambda r: r["kind"] == "primary" and r["world"] == 0 and r["probe"] == "P12"))
    with pytest.raises(mp.AuditError, match="duplicated identity"):
        mp.audit_family(unit, splits["test"][0], real=False, allowances=(64, 256))


def test_family_audit_rejects_an_unexpected_cell(splits, family_run, tmp_path):
    directory, _, _ = family_run
    unit = _copy_unit(directory, tmp_path / "T00")
    _rewrite(unit, "assessments.jsonl", lambda rows: _first(
        rows, lambda r: r["kind"] == "reference" and r["condition"] == "no_memory",
        lambda r: r.update(condition="extra_condition")))
    with pytest.raises(mp.AuditError):
        mp.audit_family(unit, splits["test"][0], real=False, allowances=(64, 256))


def test_qualification_gate_rejects_duplicated_row_instead_of_scoring_it(splits, tmp_path):
    mp.run_qualification(splits["qualification"], tmp_path / "q", FixtureModel(), commit=lambda: None)
    _rewrite(tmp_path / "q", "assessments.jsonl", lambda rows: _swap_row(
        rows, lambda r: r["family_id"] == "Q01" and r["condition"] == "full_history" and r["world"] == 2,
        lambda r: r["family_id"] == "Q01" and r["condition"] == "full_history" and r["world"] == 1))
    with pytest.raises(mp.AuditError, match="duplicated identity"):
        mp.qualification_gate(tmp_path / "q", splits["qualification"])


def test_s1_with_unauditable_pilot_records_error_and_no_budget_decision(splits, tmp_path, monkeypatch):
    package = _package(tmp_path, splits)
    real_audit = mp.audit_family

    def failing_audit(directory, family, **kwargs):
        if family["family_id"] == "D01":
            raise mp.AuditError("synthetic pilot audit failure")
        return real_audit(directory, family, **kwargs)
    monkeypatch.setattr(mp, "audit_family", failing_audit)
    log, commit = commit_log()
    with pytest.raises(mp.AuditError, match="pilot incomplete: synthetic pilot audit failure"):
        mp.run_stage("s1", package, tmp_path / "s1", FixtureModel(), commit=commit)
    status = json.loads((tmp_path / "s1" / "stage-status.json").read_text())
    assert status["outcome"] == "error" and status["qualification"]["passed"]
    assert status["pilot"] == {"complete": False, "stop": None, "low": None,
                               "reason": "synthetic pilot audit failure"}
    assert log[-1] == "commit"


def test_s1_complete_pilot_reports_decision(splits, tmp_path):
    status = mp.run_stage("s1", _package(tmp_path, splits), tmp_path / "s1", FixtureModel(),
                          commit=lambda: None)
    assert status["outcome"] == "pilot_complete" and status["pilot"]["complete"] is True
    assert status["pilot"]["low"] == 64 and status["qualification"]["distinct_prompts"] == 76


def _repair_unit(tmp_path, family, raw='{"a":1,"a":2}'):
    outputs = iter([raw, '{"a":"blue"}'])

    def writer(payload, fmt, purpose):
        if payload["last_event"] == mp.INITIAL:
            return next(outputs)
        return payload["previous_memory"]
    unit_dir = tmp_path / "repair"
    unit = mp._Unit(unit_dir, FixtureModel(writer=writer), float("inf"), lambda: 0.0)
    unit.chain(family, family["worlds"][0], "json", 256)
    unit.complete({}, lambda: None)
    mp.audit_unit(unit_dir, [family], real=False)  # honest repair passes
    return unit_dir


def _is_repair(r):
    return r["event"] == "model_request" and r["purpose"] == "memory_repair"


@pytest.mark.parametrize("change", [
    lambda r: r["messages"][-1].update(content=r["messages"][-1]["content"].replace(
        "Return only the replacement memory.", "Return only the replacement memory. Be brief.")),
    lambda r: r["messages"].append({"role": "user", "content": "Also keep pulse names."}),
    lambda r: r["messages"][-1].update(content=r["messages"][-1]["content"].replace(
        "duplicate_json_key", "malformed_json")),
])
def test_auditor_rejects_a_changed_or_extended_repair_request(splits, tmp_path, change):
    family = splits["test"][0]
    unit_dir = _repair_unit(tmp_path, family)
    _rewrite(unit_dir, "events.jsonl", lambda rows: _first(rows, _is_repair, change))
    with pytest.raises(mp.AuditError, match="v17 repair policy"):
        mp.audit_unit(unit_dir, [family], real=False)


def test_auditor_rejects_recorded_events_that_differ_from_routing(splits, tmp_path):
    family = splits["test"][0]
    unit_dir = _repair_unit(tmp_path, family)
    _rewrite(unit_dir, "writes.jsonl", lambda rows: _first(
        rows, lambda r: r["write_index"] == 0, lambda r: r.update(update_events=["memory_accepted"])))
    with pytest.raises(mp.AuditError, match="reconstructed routing"):
        mp.audit_unit(unit_dir, [family], real=False)
