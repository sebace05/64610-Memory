"""Offline base-rate tests; fixture scores/token counts never establish Qwen ability."""
import json
from pathlib import Path
import re
import shutil

import pytest

from game_memory import reader_base_rate as br
from test_reader_diagnostic import FixtureModel


class Reader(FixtureModel):
    def answer(self, messages):
        user = messages[1].content
        memory = user.split("Retained context:\n", 1)[1].split("\n\nCurrent query:", 1)[0]
        query = user.split("What is ", 1)[1].split("'s current", 1)[0]
        options = [line[3:] for line in user.split("destination?\n", 1)[1].splitlines()]
        state = (json.loads(memory) if memory.startswith("{") else
                 {n.lower(): v for n,v in re.findall(r"([A-Za-z0-9-]+) is assigned to (\w+)\.", memory)})
        return self.force or br.mp.LABELS[options.index(state.get(query) or br.mp.ABSTAIN)]

    def generate(self, *args, **kwargs):
        pytest.fail("base-rate path attempted generation/writing")


@pytest.fixture(scope="module")
def inputs():
    fs = br.families()
    return fs, br.cases(fs)


@pytest.fixture(scope="module")
def package(tmp_path_factory):
    path = tmp_path_factory.mktemp("base-rate-package")/"package"
    br.prepare(path)
    return path


def test_fresh_population_balanced_disjoint_and_deterministic(inputs):
    fs, entries = inputs
    assert fs == br.families()
    assert len(fs) == 160 and len(entries) == len({c["prompt_sha256"] for c in entries}) == 2560
    assert sum(f["query_type"] == "updated" for f in fs) == 80
    ids = [n for f in fs for n in f["numbered_names"].values()]
    assert len(ids) == len(set(ids)) == 1280 and all(re.fullmatch(r"item-[1-9][0-9]{3}", n) for n in ids)
    old = [f for groups in (br.mp.generate_splits(), br.wc.generate_splits()) for fs in groups.values() for f in fs]
    previous_names = {n for f in old for n in [*f["order"], *f["pulses"]]}
    assert not previous_names & {n for f in fs for n in [*f["order"], *f["pulses"]]}
    assert not {br.mp._composition(f) for f in old} & {br.mp._composition(f) for f in fs}
    olds = [f["base"][f["roles"]["target"]] for f in fs if f["query_type"] == "updated"]
    assert all(olds.count(color) == 20 for color in br.mp.DESTINATIONS)


def test_paired_prompts_change_only_identifiers_and_format(inputs):
    fs, entries = inputs
    indexed = {c["case_id"]: c for c in entries}
    for f in fs:
        for world in range(4):
            for fmt in br.mp.FORMATS:
                a = indexed[f"{f['family_id']}/{world}/opaque/{fmt}"]
                b = indexed[f"{f['family_id']}/{world}/numbered/{fmt}"]
                assert a["gold"] == b["gold"] and a["options"] == b["options"]
                assert list(a["state"].values()) == list(b["state"].values())
                assert b["entity_order"] == [f["numbered_names"][n] for n in a["entity_order"]]
                assert a["state"][a["query"]] == b["state"][b["query"]] == a["gold"]
            for arm in br.ARMS:
                a,b = (indexed[f"{f['family_id']}/{world}/{arm}/{fmt}"] for fmt in br.mp.FORMATS)
                assert a["entity_order"] == b["entity_order"]
                assert a["state"] == b["state"]
                assert list(json.loads(b["memory"])) == a["entity_order"]
                assert a["messages"] == [br.asdict(m) for m in br.mp.reader_messages(a["memory"],a["query"],a["options"])]


def test_frozen_settings_and_package_sources(package, tmp_path):
    m,fs,entries = br.verify_package(package, Path.cwd())
    assert m["gpu"] == "NVIDIA A10" and m["request_ceiling"] == 2608
    assert len(br.sentinels(entries)) == 16
    with pytest.raises(FileExistsError):br.prepare(package)


def test_device_mismatch_refuses_before_tokenizer_or_weights(tmp_path, monkeypatch):
    from game_memory import transformers_model as tm
    monkeypatch.setattr(br.rd.transport,"runtime_and_cache",lambda *_: ({"runtime":{"gpu":"NVIDIA A10G"}},{}))
    monkeypatch.setattr(br.rd.transport,"cached_tokenizer",lambda *_: pytest.fail("wrong GPU reached tokenizer"))
    monkeypatch.setattr(tm,"TransformersModel",lambda *_: pytest.fail("wrong GPU loaded weights"))
    with pytest.raises(ValueError,match="before weights"):
        br.load_models(br.settings(),[],tmp_path)


def test_budget_bounds_and_writer_exclusion():
    budget = br._Budget(10,lambda:0,1)
    reader = br._Reader(Reader(),budget)
    with pytest.raises(ValueError):reader.generate([],purpose="memory")
    budget.check()
    with pytest.raises(RuntimeError,match="ceiling"):budget.check()
    with pytest.raises(TimeoutError):br._Budget(0,lambda:0,1).check()


@pytest.fixture(scope="module")
def completed(package,tmp_path_factory):
    path = tmp_path_factory.mktemp("base-rate-run")/"run"
    model,reference = Reader(),Reader()
    commits = []
    result = br.run(package,path,loader=lambda *_:(model,reference),commit=lambda:commits.append(model.calls))
    return path,result,model,reference,commits


def test_full_fixture_run_has_exact_primary_check_counts_and_durable_families(completed):
    path,r,model,reference,commits = completed
    assert r["status"]["complete"] and r["status"]["model_is_fake"]
    assert model.calls == 2592 and reference.calls == 16
    assert r["known_usage"]["requests"] == r["known_usage"]["responses"] == 2608
    assert r["primary_assessments"] == 2560 and r["completed_family_count"] == 160
    assert commits[:3] == [0,16,32] and len(commits) == 164
    assert all(c["accuracy"] == 1 for c in r["analysis"]["cells"].values())
    assert r["analysis"]["decision"]["result"] == "low_observed_error"
    assert all(x["repeat_label_agrees"] and x["corpus_replay_label_agrees"] for x in r["checks"])


def _synthetic_rows(entries, bad):
    return [dict(case_id=c["case_id"],correct=not bad(c)) for c in entries]


def test_statistics_cluster_related_siblings_and_use_paired_effects(inputs):
    fs,entries = inputs
    bad = {f"F{i:03d}" for i in range(20)}
    r = br.analyze(fs,entries,_synthetic_rows(entries,lambda c:c["family_id"] in bad and c["arm"]=="opaque"))
    assert r["cells"]["opaque/json"]["errors"] == 80
    assert r["cells"]["opaque/json"]["affected_families"] == 20
    assert r["effects"]["pooled"]["value"] == .125
    assert r["effects"]["pooled"]["ci95"][0] < .10 and r["effects"]["pooled"]["ci95"][1] > .15
    assert r["decision"]["result"] == "alternative_materially_better"
    assert r["cells"]["numbered/json"]["family_error_wilson95"][1] > .02


def test_zero_paired_variance_does_not_establish_equivalence(inputs):
    fs,entries = inputs
    bad = {f"F{i:03d}" for i in range(20)}
    r = br.analyze(fs,entries,_synthetic_rows(entries,lambda c:c["family_id"] in bad))
    assert r["effects"]["pooled"]["ci95"] == [0,0]
    assert r["effects"]["pooled"]["degenerate"]
    assert r["decision"]["result"] == "inconclusive"


def test_similar_point_estimates_with_wide_uncertainty_are_inconclusive():
    cells = {"any":dict(error_rate=dict(value=.10))}
    effects = {k:dict(value=0,ci95=[-.05,.05],degenerate=False) for k in ("pooled","prose","json")}
    assert br.decide(cells,effects)["result"] == "inconclusive"
    for e in effects.values():e["ci95"]=[-.01,.01]
    assert br.decide(cells,effects)["result"] == "practically_similar"


def test_materially_worse_alternative_is_rejected_without_calling_it_inconclusive():
    cells={"any":dict(error_rate=dict(value=.1))}
    effects={k:dict(value=-.08,ci95=[-.12,-.04],degenerate=False) for k in ("pooled","prose","json")}
    assert br.decide(cells,effects)["result"]=="alternative_materially_worse"


def test_analysis_refuses_missing_or_duplicate_cases(inputs):
    fs,entries = inputs
    rows = _synthetic_rows(entries,lambda _:False)
    with pytest.raises(ValueError):br.analyze(fs,entries,rows[:-1])
    with pytest.raises(ValueError):br.analyze(fs,entries,rows+[rows[0]])


def test_interruption_preserves_completed_units_and_no_final_decision(package,tmp_path):
    model = Reader(fail_after=20)
    output = tmp_path/"partial"
    with pytest.raises(RuntimeError,match="fixture inference interruption"):
        br.run(package,output,loader=lambda *_:(model,Reader()))
    r = br.report(output)
    assert r["analysis"] is None and not r["status"]["complete"]
    assert r["completed_family_count"] == 1 and r["primary_assessments"] == 16
    assert r["known_usage"]["requests"] == 21 and r["known_usage"]["responses"] == 20
    assert r["known_usage"]["unknown_usage_requests"] == 1
    assert not (output/"completion.json").exists()


@pytest.mark.parametrize("fault",["prediction","prompt","missing","duplicate","fake_identity"])
def test_unit_audit_detects_tampering_after_rehash(completed,inputs,tmp_path,fault):
    path,_,_,_,_ = completed
    unit = tmp_path/"F000"
    shutil.copytree(path/"F000",unit)
    name = "events.jsonl" if fault=="prompt" else "assessments.jsonl"
    rows = br.rd._rows(unit/name)
    if fault=="prompt":rows[0]["messages"][1]["content"] += " changed"
    elif fault=="prediction":rows[0]["selected_destination"]="invented"
    elif fault=="missing":rows.pop()
    elif fault=="duplicate":rows[-1]=rows[0]
    else:
        summary = br.rd._read(unit/"summary.json");summary["model_identity"]="incorrect"
        (unit/"summary.json").write_text(json.dumps(summary))
    (unit/name).write_text(''.join(json.dumps(r)+'\n' for r in rows))
    ledger = br.rd._read(unit/"completion.json")
    for file in ledger["files"]:ledger["files"][file]=br.mp.file_sha256(unit/file)
    (unit/"completion.json").write_text(json.dumps(ledger))
    selected = [c for c in inputs[1] if c["family_id"]=="F000"]
    with pytest.raises(ValueError):br.audit_unit(unit,[(c,"restricted") for c in selected],Reader().metadata)


def test_explicit_recovery_only_copies_hash_pinned_complete_units(package,completed,tmp_path):
    path,_,_,_,_ = completed
    manifest = br.rd._read(path/"entry.json")["manifest"]
    reuse=[dict(family_id="F000",directory=str(path/"F000"),manifest_sha256=manifest["manifest_sha256"],
                completion_sha256=br.mp.file_sha256(path/"F000/completion.json"))]
    model,reference = Reader(),Reader()
    output = tmp_path/"recovered"
    r = br.run(package,output,loader=lambda *_:(model,reference),reuse=reuse)
    assert r["status"]["complete"] and r["status"]["reused_requests"]==16
    assert r["status"]["new_attempted_requests"]==2592
    assert model.calls+reference.calls==2592
    for p in (path/"F000").iterdir():assert p.read_bytes()==(output/"F000"/p.name).read_bytes()
    reuse[0]["completion_sha256"]="bad"
    with pytest.raises(ValueError,match="identity"):
        br.run(package,tmp_path/"bad",loader=lambda *_:pytest.fail("bad recovery loaded weights"),reuse=reuse)


def _all_sources(path):
    manifest = br.rd._read(path/"entry.json")["manifest"]
    return [dict(family_id=f"F{i:03d}",directory=str(path/f"F{i:03d}"),
        manifest_sha256=manifest["manifest_sha256"],completion_sha256=br.mp.file_sha256(path/f"F{i:03d}/completion.json"))
        for i in range(br.N)]


def test_independent_mismatch_preserves_complete_primary_data_without_final_decision(package,completed,tmp_path):
    class WrongReference(Reader):
        def score_choices(self,messages,*,labels):
            result = super().score_choices(messages,labels=labels)
            wrong = labels[(labels.index(result.text)+1)%len(labels)]
            meta = dict(result.metadata,candidate_logits=[2 if label==wrong else 0 for label in labels])
            return br.Generation(wrong,result.input_tokens,1,result.elapsed_seconds,meta)
    output = tmp_path/"mismatch"
    with pytest.raises(ValueError,match="independent scoring mismatch"):
        br.run(package,output,loader=lambda *_:(Reader(),WrongReference()),reuse=_all_sources(completed[0]))
    r = br.report(output)
    assert r["completed_family_count"]==160 and r["analysis"] is None
    assert not r["status"]["complete"] and not (output/"completion.json").exists()


def test_repeat_instability_is_reported_without_replacing_primary_answers(package,completed,tmp_path):
    class Drifting(Reader):
        def answer(self,messages):
            label = super().answer(messages)
            return br.mp.LABELS[(br.mp.LABELS.index(label)+1)%5] if self.calls>16 else label
    output = tmp_path/"unstable"
    r = br.run(package,output,loader=lambda *_:(Drifting(),Reader()),reuse=_all_sources(completed[0]))
    assert r["status"]["complete"] and r["status"]["new_attempted_requests"]==48
    assert any(not c["repeat_label_agrees"] for c in r["checks"])
    assert all(c["accuracy"]==1 for c in r["analysis"]["cells"].values())


def test_changed_device_setting_rejected_even_if_manifest_is_rehashed(package,tmp_path):
    path = tmp_path/"package";shutil.copytree(package,path)
    manifest = br.rd._read(path/"manifest.json");manifest["gpu"]="NVIDIA A10G"
    manifest["manifest_sha256"]=br.mp.digest({k:v for k,v in manifest.items() if k!="manifest_sha256"})
    (path/"manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match="settings"):
        br.verify_package(path)


def test_import_and_help_do_not_load_optional_inference_libraries():
    import subprocess
    import sys
    code="""import sys
from game_memory import reader_base_rate
assert not {'torch','transformers','modal'} & set(sys.modules)
sys.argv=['reader-base-rate','--help'];reader_base_rate.main()
"""
    result=subprocess.run([sys.executable,"-c",code],capture_output=True,text=True,timeout=15)
    assert result.returncode==0 and 'prepare' in result.stdout
