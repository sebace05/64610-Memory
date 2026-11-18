"""Offline behavior checks; synthetic text and predictions never establish capability."""
import copy
import json
import math
from pathlib import Path

import pytest

from game_memory import paper_memory as pm
from game_memory.components import Generation


class FixtureModel:
    metadata = dict(is_fake=True, model_id="synthetic-paper-fixture")

    def __init__(self, *, bad_writes=(), fail_at=None):
        self.calls = []
        self.bad_writes = list(bad_writes)
        self.fail_at = fail_at

    def count_tokens(self, text):
        return math.ceil(len(text) / 4)

    def generate(self, messages, *, purpose):
        self.calls.append((messages, purpose))
        if len(self.calls) == self.fail_at:
            raise RuntimeError("synthetic transport interruption")
        if purpose != "action":
            payload = json.loads(messages[1].content)
            facts = " ".join(part for part in (payload["previous_memory"], payload["chunk"])
                             if "orbits" in part)
            # Keep just the supplied literal sentences, irrespective of question.
            import re
            facts = " ".join(dict.fromkeys(re.findall(r"\b[A-Z][a-z]+ has \d+ orbits\.", facts)))
            text = (json.dumps(dict(facts=facts)) if "JSON object" in messages[0].content else facts)
            if self.bad_writes:
                text = self.bad_writes.pop(0)
        else:
            import re
            user = messages[1].content
            entity = user.rsplit("Question:\n", 1)[1].split()[-1].rstrip("?")
            context = user.split("\n\nQuestion:\n", 1)[0]
            match = re.search(rf"{entity} has (\d+) orbits", context)
            text = match[1] if match else pm.ABSTAIN
            # Deliberate ordinary error; it must stay in the scored denominator.
            if entity == "Gamma" and "Title:" in context:
                text = "999"
        return Generation(text, 10, self.count_tokens(text), .01)


@pytest.fixture(scope="module")
def package(tmp_path_factory):
    root = tmp_path_factory.mktemp("paper-inputs")
    papers = []
    for i in range(3):
        paragraphs = [dict(section="Setup", text="Alpha has 17 orbits. " + "filler " * 450),
                      dict(section="Results", text="Beta has 56 orbits. Gamma has 300 orbits. " + "filler " * 450)]
        questions = [dict(question_id=f"P{i:02}/Q{j}", question=f"How many orbits for {name}?",
                          gold_anchor=value, aliases=[value], evidence_index=idx,
                          evidence_text=paragraphs[idx]["text"])
                     for j, (name, value, idx) in enumerate((("Alpha", "17", 0), ("Beta", "56", 1), ("Gamma", "300", 1)))]
        papers.append(dict(paper_id=f"P{i:02}", qasper_id="synthetic", title="Synthetic paper",
                           abstract="A fixture only.", paragraphs=paragraphs, questions=questions))
    data = dict(version=pm.VERSION, is_fake=True, papers=papers)
    path = root / "fixture.json"
    path.write_text(json.dumps(data))
    pm.prepare(root / "package", path)
    return root / "package"


@pytest.fixture(scope="module")
def completed(package, tmp_path_factory):
    output = tmp_path_factory.mktemp("paper-output") / "run"
    model, commits = FixtureModel(), []
    report = pm.run(package, output, "P00", loader=lambda *_: model,
                    commit=lambda: commits.append(len(model.calls)))
    return output, report, model, commits


def test_real_inputs_literal_gold_and_no_optional_import():
    data = pm.transport.read(Path(pm.__file__).resolve().parents[1] / pm.DATA)
    papers = pm.validate_data(data)
    assert not data["is_fake"] and len(papers) == 3
    assert pm.mp.file_sha256(Path(pm.__file__).resolve().parents[1] / pm.DATA) == pm.DATA_SHA
    for p in papers:
        assert "\n\n".join(pm.chunks(p)) == pm.full_text(p)
        for q in p["questions"]:
            assert q["gold_anchor"] in q["evidence_text"]


def test_streaming_prompts_exclude_questions_and_preserve_only_supplied_state(package):
    _, papers = pm.verify_package(package, Path.cwd())
    paper = papers[0]
    for cls in pm.WRITERS.values():
        writer = cls()
        messages = writer._messages("old notebook", "forbidden action", "new text", pm.PaperContext(), pm.BUDGET)
        payload = json.loads(messages[1].content)
        assert payload == dict(previous_memory="old notebook", chunk="new text", memory_token_limit=2048)
        assert "forbidden action" not in str(messages)
        assert all(q["question"] not in str(messages) for q in paper["questions"])
        assert "recipe" not in str(messages)
    assert "\n\n".join(pm.chunks(paper)) == pm.full_text(paper)
    oversized = copy.deepcopy(paper)
    oversized["paragraphs"] = [dict(section="Long", text="x" * 7000)]
    assert "x" * 7000 in pm.chunks(oversized)[-1]


def test_all_conditions_count_errors_and_controls_without_accuracy_gate(completed, package):
    output, report, model, commits = completed
    assert report["status"]["complete"] and report["status"]["model_is_fake"]
    assert report["metrics"]["prose"]["correct"] == report["metrics"]["json"]["correct"] == 3
    assert report["metrics"]["full_paper"]["correct"] == 2
    assert report["metrics"]["no_context"] == dict(correct=0, total=3, token_f1=0.0, abstentions=3)
    assert len(report["rows"]) == 20 and not report["repeat_disagreements"]
    assert report["known_usage"]["requests"] == len(model.calls) == 24
    assert report["known_usage"]["unknown_usage_requests"] == 0
    assert commits[0] == 0 and all(c in commits for c in range(1, 25))
    assert pm.report(output) == report
    with pytest.raises(FileExistsError):
        pm.run(package, output, "P00", loader=lambda *_: pytest.fail("replayed"))


@pytest.mark.parametrize("raw,aliases,exact", [
    (' Answer: “1,120”. ', ["1120"], True),
    ('Answer: "1,120"', ["1120"], True),
    ("1,120.", ["1120"], True),
    ("-3.2", ["3.2"], False), ("10%", ["10"], False),
    ("The Switchboard corpus", ["Switchboard corpus"], False),
    ("", ["17"], False), (pm.ABSTAIN, ["17"], False),
])
def test_fixed_short_answer_scoring(raw, aliases, exact):
    result = pm.grade(raw, aliases)
    assert result["correct"] is exact
    assert 0 <= result["token_f1"] <= 1


@pytest.mark.parametrize("bad", ["x" * 9000, "", "not JSON"])
def test_repair_and_fallback_replay(package, tmp_path, bad):
    # Force two invalid prose size candidates, or JSON syntax candidates.
    if bad == "x" * 9000:
        outputs = [bad, bad]
    else:
        outputs = ["Alpha has 17 orbits.", "Alpha has 17 orbits. Beta has 56 orbits. Gamma has 300 orbits.", bad, bad]
    model = FixtureModel(bad_writes=outputs)
    output = tmp_path / "run"
    report = pm.run(package, output, "P00", loader=lambda *_: model)
    assert report["known_usage"]["repairs"] >= 1
    assert any("memory_fallback:previous_valid_memory" in w["update_events"]
               for fmt in pm.WRITERS for w in pm.mp._jsonl(output / fmt / "writes.jsonl"))
    assert report["metrics"]["prose"]["total"] == report["metrics"]["json"]["total"] == 3


def test_interruption_retains_raw_error_and_known_usage(package, tmp_path):
    model = FixtureModel(fail_at=2)
    output = tmp_path / "run"
    with pytest.raises(RuntimeError, match="synthetic transport"):
        pm.run(package, output, "P00", loader=lambda *_: model)
    report = pm.report(output)
    assert not report["status"]["complete"]
    assert report["known_usage"]["requests"] == 2
    assert report["known_usage"]["responses"] == 1
    assert report["known_usage"]["unknown_usage_requests"] == 1
    assert pm.mp._jsonl(output / "prose" / "events.jsonl")[-1]["event"] == "model_error"


def test_call_ceiling_stops_before_delegation():
    model = FixtureModel()
    limited = pm._LimitedModel(model, 0, 10, lambda: 0)
    with pytest.raises(pm.mp.StageTimeout):
        limited.generate(pm.reader_messages("", "anything"), purpose="action")
    assert not model.calls


def test_real_loader_refuses_fixture_before_import(package, tmp_path):
    manifest, papers = pm.verify_package(package)
    with pytest.raises(ValueError, match="fake papers"):
        pm.load_model(manifest, papers[0], tmp_path)


@pytest.mark.parametrize("fault", ["prompt", "grading", "token_count", "missing_response"])
def test_resealed_corruption_is_caught(completed, tmp_path, fault):
    import shutil
    source = completed[0]
    output = tmp_path / "copy"
    shutil.copytree(source, output)
    unit = output / ("prose" if fault == "token_count" else "reader")
    filename = ("writes.jsonl" if fault == "token_count" else
                "assessments.jsonl" if fault == "grading" else "events.jsonl")
    rows = pm.mp._jsonl(unit / filename)
    if fault == "prompt":
        rows[0]["messages"][1]["content"] += " leaked hidden evidence"
    elif fault == "grading":
        rows[0]["correct"] = not rows[0]["correct"]
    elif fault == "token_count":
        rows[0]["token_counts"][0]["count"] += 1
    else:
        rows.pop()
    (unit / filename).write_text("".join(json.dumps(r) + "\n" for r in rows))
    completion = pm.transport.read(unit / "completion.json")
    completion["files"][filename] = pm.mp.file_sha256(unit / filename)
    (unit / "completion.json").write_text(json.dumps(completion))
    with pytest.raises(ValueError):
        pm.report(output)
