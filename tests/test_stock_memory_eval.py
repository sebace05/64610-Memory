"""Offline stock-memory evaluation checks; all predictions here are fixtures."""
import copy
import json
from pathlib import Path
import shutil

import pytest

from game_memory import stock_memory_eval as sm
from test_memory_probe import FixtureModel as Writer, _rewrite
from test_reader_diagnostic import FixtureModel as Reader, note_state


class WriterFixture(Writer):
    def count_tokens(self,text):
        return 160 if text else 0  # Synthetic size deliberately selects B=256.


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    root = tmp_path_factory.mktemp("stock-corpus")
    package = root/"writer-package"
    sm.wc.prepare(package)
    writer = WriterFixture()
    path = root/"writer"
    sm.wc.calibrate(package,path,loader=lambda *_:(writer,writer.count_tokens),commit=lambda:None)
    annotations = []
    for f in sm.wc.generate_splits()["calibration"]:
        query = f["roles"]["target"]
        for s in sm.rd._rows(path/f["family_id"]/"snapshots.jsonl"):
            annotations.append(dict(snapshot_id=s["snapshot_id"],notebook_sha256=s["rendered_sha256"],query=query,
                supported_destination=note_state(s["rendered"])[query],evidence_quotes=[s["rendered"]],
                rationale="Synthetic fixture evidence, not a Qwen annotation."))
    data = dict(version=sm.VERSION,predictions_seen=False,method="synthetic pre-prediction labels",annotations=annotations)
    labels = root/"annotations.json"
    labels.write_text(json.dumps(data))
    return path,labels,data


@pytest.fixture(scope="module")
def package(corpus,tmp_path_factory):
    path = tmp_path_factory.mktemp("stock-package")/"package"
    sm.prepare(corpus[0],corpus[1],path)
    return path


@pytest.fixture(scope="module")
def completed(package,tmp_path_factory):
    path = tmp_path_factory.mktemp("stock-evaluation")/"run"
    reader,reference = Reader(),Reader()
    commits = []
    result = sm.run(package,path,loader=lambda *_:(reader,reference),commit=lambda:commits.append(reader.calls))
    return path,result,reader,reference,commits


def test_exact_original_reader_inputs_and_separate_evidence_labels(corpus,package):
    manifest,entries = sm.verify_package(package,Path.cwd())
    assert manifest["writer_is_fake"] and len(entries)==64
    assert manifest["request_ceiling"]==192
    for f in sm.FAMILIES:
        exported = sm.rd._rows(corpus[0]/f/"reader-inputs.jsonl")
        cases = [c for c in entries if c["family_id"]==f]
        assert [c["messages"] for c in cases]==[e["messages"] for e in exported]
        assert all(e["supported_label"] is None and "gold" not in e for e in exported)
        assert (corpus[0]/f/"reader-inputs.jsonl").read_bytes()==(package/"writer-evidence"/f/"reader-inputs.jsonl").read_bytes()
    assert all(c["supported_destination"]==c["gold"] for c in entries)
    with pytest.raises(FileExistsError):sm.prepare(corpus[0],corpus[1],package)


@pytest.mark.parametrize("fault",["missing","duplicate","hash","query","quote","destination","seen_predictions"])
def test_bad_annotation_coverage_and_provenance_rejected(corpus,fault):
    labels = copy.deepcopy(corpus[2])
    a = labels["annotations"][0]
    if fault=="missing":labels["annotations"].pop()
    elif fault=="duplicate":labels["annotations"][-1]=a
    elif fault=="hash":a["notebook_sha256"]="bad"
    elif fault=="query":a["query"]="not-the-query"
    elif fault=="quote":a["evidence_quotes"]=["invented evidence"]
    elif fault=="destination":a["supported_destination"]="not-a-destination"
    else:labels["predictions_seen"]=True
    with pytest.raises(ValueError):sm.inputs(corpus[0],labels)


def test_all_ordinary_predictions_count_without_accuracy_gate(completed):
    path,r,reader,reference,commits = completed
    assert r["status"]["complete"] and r["status"]["model_is_fake"]
    assert r["primary_assessments"]==64 and r["completed_family_count"]==4
    assert reader.calls==128 and reference.calls==64
    assert r["known_usage"]["requests"]==r["known_usage"]["responses"]==192
    assert r["known_usage"]["calls_by_method"]==dict(restricted=64,reference=64,repeat=64)
    assert commits[:5]==[0,16,32,48,64]
    assert all(c["questions"]==16 and c["accuracy"]==1 for c in r["analysis"]["cells"].values())
    assert all(c["repeat_logits_agree"] for c in r["checks"])
    assert sm.report(path)==r
    with pytest.raises(FileExistsError):sm.run(path/"inputs",path,loader=lambda *_:pytest.fail("resubmitted"))


def test_low_accuracy_is_a_complete_result(package,tmp_path):
    r = sm.run(package,tmp_path/"run",loader=lambda *_:(Reader(force="A"),Reader(force="A")))
    assert r["status"]["complete"]
    assert any(c["accuracy"]<.5 for c in r["analysis"]["cells"].values())


def test_evidence_agreement_and_world_accuracy_are_distinct(package):
    _,entries = sm.verify_package(package)
    cases = copy.deepcopy(entries)
    first = cases[0]
    first["supported_destination"]=sm.mp.ABSTAIN
    rows = [dict(case_id=c["case_id"],selected_destination=c["supported_destination"],
                 correct=c["supported_destination"]==c["gold"]) for c in cases]
    r = sm.analyze(cases,rows)
    cell = r["cells"][f"{first['format']}/{first['probe']}"]
    assert cell["questions"]==16 and cell["correct"]==15
    assert cell["evidence_agreement"]==1 and cell["writer_evidence_errors"]==1
    assert cell["reader_errors_on_correct_notes"]==0
    first["supported_destination"] = next(d for d in sm.mp.DESTINATIONS if d!=first["gold"])
    rows[0].update(selected_destination=first["supported_destination"],correct=False)
    cell = sm.analyze(cases,rows)["cells"][f"{first['format']}/{first['probe']}"]
    assert cell["correct"]==15 and cell["reader_evidence_errors"]==0 and cell["writer_evidence_errors"]==1


def test_wrong_lookup_on_correct_note_is_reader_error(package):
    _,cases = sm.verify_package(package)
    rows = [dict(case_id=c["case_id"],selected_destination=c["gold"],correct=True) for c in cases]
    rows[0].update(selected_destination=sm.mp.ABSTAIN,correct=False)
    result = sm.analyze(cases,rows)
    cell = result["cells"][f"{cases[0]['format']}/{cases[0]['probe']}"]
    assert cell["reader_errors_on_correct_notes"]==1 and cell["writer_evidence_errors"]==0
    assert cell["reader_evidence_errors"]==1 and cell["correct"]==15


def test_interruption_retains_partial_evidence_and_unknown_usage(package,tmp_path):
    output = tmp_path/"run"
    with pytest.raises(RuntimeError,match="interruption"):
        sm.run(package,output,loader=lambda *_:(Reader(fail_after=20),Reader()))
    r = sm.report(output)
    assert not r["status"]["complete"] and r["analysis"] is None
    assert r["completed_family_count"]==1 and r["primary_assessments"]==16
    assert r["known_usage"]["requests"]==21 and r["known_usage"]["responses"]==20
    assert r["known_usage"]["unknown_usage_requests"]==1


def test_independent_scoring_disagreement_fails_visibly(package,tmp_path):
    output = tmp_path/"run"
    with pytest.raises(ValueError,match="independent scoring mismatch"):
        sm.run(package,output,loader=lambda *_:(Reader(force="A"),Reader(force="B")))
    r = sm.report(output)
    assert r["analysis"] is None and r["known_usage"]["responses"]==65
    assert (output/"checks/events.jsonl").exists()


def test_repeat_differences_are_reported_without_changing_primary_results(package,tmp_path):
    class Changing(Reader):
        def answer(self,messages):
            return "A" if self.calls>64 else super().answer(messages)
    r = sm.run(package,tmp_path/"run",loader=lambda *_:(Changing(),Reader()))
    assert r["status"]["complete"] and any(not c["repeat_label_agrees"] for c in r["checks"])
    assert all(c["accuracy"]==1 for c in r["analysis"]["cells"].values())


def test_wrong_device_refused_before_tokenizer_and_weights(tmp_path,monkeypatch):
    from game_memory import transformers_model as tm
    monkeypatch.setattr(sm.rd.transport,"runtime_and_cache",lambda *_:({"runtime":{"gpu":"NVIDIA A10G"}},{}))
    monkeypatch.setattr(sm.rd.transport,"cached_tokenizer",lambda *_:pytest.fail("reached tokenizer"))
    monkeypatch.setattr(tm,"TransformersModel",lambda *_:pytest.fail("loaded weights"))
    with pytest.raises(ValueError,match="before tokenizer/weights"):
        sm.load_models(dict(writer_is_fake=False),[],tmp_path)


def test_real_loader_rejects_fixture_corpus_before_runtime_or_weights(tmp_path,monkeypatch):
    monkeypatch.setattr(sm.rd.transport,"runtime_and_cache",lambda *_:pytest.fail("reached GPU runtime"))
    with pytest.raises(ValueError,match="real writer corpus before weights"):
        sm.load_models(dict(writer_is_fake=True),[],tmp_path)


def test_real_reader_cannot_score_a_fixture_corpus(package,tmp_path):
    class ClaimedReal(Reader):
        metadata = {"is_fake":False,"gpu":"NVIDIA A10"}
    reader,reference = ClaimedReal(),ClaimedReal()
    with pytest.raises(ValueError,match="fixture writer corpus"):
        sm.run(package,tmp_path/"run",loader=lambda *_:(reader,reference))
    assert reader.calls==reference.calls==0


def test_analysis_rejects_dropped_or_duplicate_cases(package):
    _,cases = sm.verify_package(package)
    rows = [dict(case_id=c["case_id"],selected_destination=c["gold"],correct=True) for c in cases]
    with pytest.raises(ValueError):sm.analyze(cases,rows[:-1])
    with pytest.raises(ValueError):sm.analyze(cases,rows+[rows[0]])


def test_rehashed_falsified_answer_is_rejected(completed,tmp_path):
    output = tmp_path/"copy"
    shutil.copytree(completed[0],output)
    def change(rows):
        rows[0]["selected_destination"]="falsified"
        return rows
    _rewrite(output/"C00","assessments.jsonl",change)
    ledger = {str(p.relative_to(output)):sm.mp.file_sha256(p) for p in output.rglob('*')
              if p.is_file() and p!=output/"completion.json"}
    (output/"completion.json").write_text(json.dumps(ledger))
    with pytest.raises(ValueError,match="decision differs"):
        sm.report(output)


def test_rehashed_changed_prompt_cannot_replace_the_export(package,tmp_path):
    output = tmp_path/"copy"
    shutil.copytree(package,output)
    cases = sm.rd._read(output/"cases.json")
    cases[0]["messages"][1]["content"] += "\nHidden answer hint."
    (output/"cases.json").write_text(json.dumps(cases))
    manifest = sm.rd._read(output/"manifest.json")
    manifest["files"]["cases.json"] = sm.mp.file_sha256(output/"cases.json")
    manifest["manifest_sha256"] = sm.mp.digest({k:v for k,v in manifest.items() if k!="manifest_sha256"})
    (output/"manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match="inputs/lineage differ"):
        sm.verify_package(output)
