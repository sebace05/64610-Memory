"""Stock reader on the 64 frozen C00–C03 writer snapshots; no training or writing."""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import traceback
import zipfile

from . import memory_probe as mp
from . import reader_base_rate as br
from . import reader_diagnostic as rd
from . import writer_collection as wc
from .runner import _LoggedModel

VERSION = "stock-memory-eval-v1"
FAMILIES = ("C00", "C01", "C02", "C03")
REQUEST_CEILING = 192  # 64 primary + 64 independent reference + 64 repeats
SOFT_SECONDS = 600
WRITER_MANIFEST = "7eb254a9de27d8176c3d208c59c691e0b1b8e27b9a804e6ec79cb60660455a2d"
WRITER_COMPLETION = "54757eb5509fd97b7c39f6c6178ff8d9c27ab3162a04f750625e5265107d6376"
SOURCE_FILES = (*br.SOURCE_FILES, "game_memory/stock_memory_eval.py",
                "tests/test_stock_memory_eval.py", "docs/stock-memory-eval-v1.md")


def settings():
    return dict(version=VERSION, families=list(FAMILIES), allowance=256,
        primary_assessments=64, request_ceiling=REQUEST_CEILING,
        soft_seconds=SOFT_SECONDS, execution_seconds=900, gpu=br.GPU,
        model=dict(id=mp.MODEL_ID, revision=mp.MODEL_REVISION, dtype="float16",
                   context_limit=8192, generation_seed=0))


def inputs(corpus, annotations):
    """Audit the writer corpus and join separate, pre-prediction evidence labels."""
    corpus = Path(corpus)
    evidence = wc.report(corpus)
    if not evidence["complete"] or evidence["selected_allowance"] != 256:
        raise ValueError("requires complete B=256 writer calibration")
    origin = rd._read(corpus/"entry.json")["manifest"]
    if origin["manifest_sha256"] != mp.digest({k:v for k,v in origin.items() if k!="manifest_sha256"}):
        raise ValueError("writer manifest identity differs")
    fake = evidence["status"]["model_is_fake"]
    if not fake and (origin["manifest_sha256"] != WRITER_MANIFEST
                     or mp.file_sha256(corpus/"completion.json") != WRITER_COMPLETION):
        raise ValueError("not the frozen real writer corpus")
    fs = rd._read(corpus/"calibration-families.json")
    if fs != wc.generate_splits()["calibration"] or tuple(f["family_id"] for f in fs) != FAMILIES:
        raise ValueError("calibration families differ")
    if (annotations.get("version") != VERSION or annotations.get("predictions_seen") is not False
            or not annotations.get("method")):
        raise ValueError("pre-prediction annotation provenance missing")
    labels = annotations["annotations"]
    expected_ids = [f"{fid}/{w}/{fmt}/256/{probe}" for fid in FAMILIES
                    for w in range(4) for fmt in mp.FORMATS for probe in mp.PROBES]
    mp._require_exact([a["snapshot_id"] for a in labels], expected_ids, "evidence annotations")
    labels = {a["snapshot_id"]:a for a in labels}
    entries = []
    for f in fs:
        fid = f["family_id"]
        snapshots = {s["snapshot_id"]:s for s in rd._rows(corpus/fid/"snapshots.jsonl")}
        for exported in rd._rows(corpus/fid/"reader-inputs.jsonl"):
            sid = exported["snapshot_id"]
            note, annotation = snapshots[sid], labels[sid]
            query, options = f["roles"]["target"], f["options"]
            supported = annotation["supported_destination"]
            quotes = annotation["evidence_quotes"]
            if (annotation["notebook_sha256"] != note["rendered_sha256"]
                    or annotation["query"] != query or supported not in options
                    or not annotation["rationale"] or not isinstance(quotes,list)
                    or any(not isinstance(q,str) or not q or q not in note["rendered"] for q in quotes)
                    or (supported != mp.ABSTAIN and not any(query.casefold() in q.casefold() and supported in q for q in quotes))):
                raise ValueError("annotation differs from supplied note/query or lacks evidence")
            messages = [asdict(m) for m in mp.reader_messages(note["rendered"],query,options)]
            if exported["messages"] != messages or exported["supported_label"] is not None:
                raise ValueError("original reader export changed")
            entries.append(dict(case_id=sid, family_id=fid, world=note["world"],
                format=note["format"], probe=note["probe"], allowance=256,
                query_type=f["query_type"], query=query, options=options,
                gold=f["worlds"][note["world"]]["answer"],
                supported_destination=supported, supported_label=mp.LABELS[options.index(supported)],
                annotation=annotation, memory=note["rendered"], notebook_sha256=note["rendered_sha256"],
                messages=messages, prompt_sha256=exported["prompt_sha256"]))
    mp._require_exact([c["case_id"] for c in entries],expected_ids,"stock memory cases")
    return entries, dict(writer_is_fake=fake, writer_manifest=origin["manifest_sha256"],
                         writer_completion_sha256=mp.file_sha256(corpus/"completion.json"))


def prepare(corpus, annotations, output):
    annotations = rd._read(annotations)
    entries, lineage = inputs(corpus, annotations)
    output = Path(output)
    output.mkdir(parents=True,exist_ok=False)
    shutil.copytree(corpus,output/"writer-evidence")
    rd.transport.save(output/"annotations.json",annotations)
    rd.transport.save(output/"cases.json",entries)
    source = Path(__file__).resolve().parents[1]
    with zipfile.ZipFile(output/"source.zip","x",compression=zipfile.ZIP_DEFLATED) as archive:
        for name in SOURCE_FILES:
            archive.write(source/name,name)
    manifest = dict(**settings(),**lineage,
        unique_prompts=len({c["prompt_sha256"] for c in entries}),
        files={str(p.relative_to(output)):mp.file_sha256(p) for p in sorted(output.rglob('*')) if p.is_file()},
        source_files={n:mp.file_sha256(source/n) for n in SOURCE_FILES})
    manifest["manifest_sha256"] = mp.digest(manifest)
    rd.transport.save(output/"manifest.json",manifest)
    return manifest


def verify_package(package,source=None):
    package = Path(package)
    manifest = rd._read(package/"manifest.json")
    if (manifest["manifest_sha256"] != mp.digest({k:v for k,v in manifest.items() if k!="manifest_sha256"})
            or any(manifest.get(k)!=v for k,v in settings().items())):
        raise ValueError("stock evaluation manifest/settings differ")
    mp._require_exact(list(manifest["files"]), [str(p.relative_to(package)) for p in package.rglob('*')
        if p.is_file() and p!=package/"manifest.json"],"stock package files")
    for name,expected in manifest["files"].items():
        if Path(name).is_absolute() or ".." in Path(name).parts or mp.file_sha256(package/name)!=expected:
            raise ValueError("stock package path/bytes differ")
    with zipfile.ZipFile(package/"source.zip") as archive:
        if sorted(archive.namelist())!=sorted(SOURCE_FILES) or set(manifest["source_files"])!=set(SOURCE_FILES):
            raise ValueError("stock source inventory differs")
        for name,expected in manifest["source_files"].items():
            if hashlib.sha256(archive.read(name)).hexdigest()!=expected:
                raise ValueError("archived stock source differs")
            if source is not None and mp.file_sha256(Path(source)/name)!=expected:
                raise ValueError("current stock source differs: "+name)
    entries,lineage = inputs(package/"writer-evidence",rd._read(package/"annotations.json"))
    if (entries!=rd._read(package/"cases.json") or any(manifest.get(k)!=v for k,v in lineage.items())
            or manifest["unique_prompts"]!=len({c["prompt_sha256"] for c in entries})):
        raise ValueError("frozen stock inputs/lineage differ")
    return manifest,entries


def load_models(manifest,entries,output):
    if manifest.get("writer_is_fake") is not False:
        raise ValueError("real loader requires the frozen real writer corpus before weights")
    from . import transformers_model as tm
    os.environ.update(rd.transport.ENV)
    config = tm.TransformersConfig(revision=mp.MODEL_REVISION,dtype="float16",device="cuda",
        context_limit=8192,action_max_new_tokens=32,memory_max_new_tokens=1024,
        generation_seed=0,local_files_only=True)
    cache = Path("/cache/huggingface/hub/models--Qwen--Qwen3-4B-Instruct-2507/snapshots")/mp.MODEL_REVISION
    runtime,cfg = rd.transport.runtime_and_cache(tm,config,cache)
    rd.transport.save(output/"runtime-cache.json",runtime)
    if runtime["runtime"]["gpu"]!=br.GPU:
        raise ValueError("pinned NVIDIA A10 required; refused before tokenizer/weights")
    tokenizer = rd.transport.cached_tokenizer(cache)
    checked = rd.preflight(entries,tokenizer,cfg["vocab_size"],evidence="actual_cached_tokenizer")
    if (len(checked["prompts"])!=manifest["unique_prompts"]
            or checked["template_sha256"]!="64f85b198065d0fba2a81f37e10ed68161ce2c19a754c7100e67e0ca2ee9c326"):
        raise ValueError("actual prompt/template coverage differs")
    rd.transport.save(output/"tokenizer-preflight.json",checked)
    model = tm.TransformersModel(config)
    rd.transport.save(output/"model.json",model.metadata)
    return model,rd.ReferenceModel(model)


def run(package,output,*,loader=load_models,commit=lambda:None,clock=time.monotonic):
    manifest,entries = verify_package(package,Path(__file__).resolve().parents[1])
    output = Path(output)
    output.mkdir(parents=True,exist_ok=False)
    started = clock()
    shutil.copytree(package,output/"inputs")
    rd.transport.save(output/"entry.json",dict(manifest=manifest))
    commit()
    deadline = started+SOFT_SECONDS
    budget,original = None,None
    status = dict(complete=False,completed_families=[],manifest_sha256=manifest["manifest_sha256"])
    try:
        model,reference = loader(manifest,entries,output)
        status.update(model_is_fake=model.metadata.get("is_fake") is not False,
                      reference_is_fake=reference.metadata.get("is_fake") is not False)
        if status["model_is_fake"]!=status["reference_is_fake"]:
            raise ValueError("mixed real/fixture readers")
        if not status["model_is_fake"] and (model.metadata.get("gpu")!=br.GPU or manifest["writer_is_fake"]):
            raise ValueError("unpinned GPU or fixture writer corpus with real reader")
        if not (output/"model.json").exists():
            rd.transport.save(output/"model.json",model.metadata)
        budget = br._Budget(deadline,clock,REQUEST_CEILING)
        primary,other = br._Reader(model,budget),br._Reader(reference,budget)
        predictions = {}
        for fid in FAMILIES:
            unit = mp._Unit(output/fid,primary,deadline,clock)
            try:
                for c in entries:
                    if c["family_id"]==fid:
                        predictions[c["case_id"]] = br._score(unit,unit.logged,c,"restricted")
                unit.complete(dict(requests=unit.request_id+1,model_identity=mp.digest(model.metadata)),commit)
            finally:
                unit.close()
            status["completed_families"].append(fid)
        unit = mp._Unit(output/"checks",primary,deadline,clock)
        try:
            reference_log = _LoggedModel(other,unit._emit,lambda:0)
            for c in entries:
                checked = br._score(unit,reference_log,c,"reference")
                if not rd.compare_scores(predictions[c["case_id"]],checked):
                    raise ValueError("independent scoring mismatch; preserve raw evidence")
            for c in entries:
                br._score(unit,unit.logged,c,"repeat")
            unit.complete(dict(requests=unit.request_id+1,model_identity=mp.digest(model.metadata)),commit)
        finally:
            unit.close()
        status.update(complete=True,outcome="stock_memory_evaluation_complete")
    except BaseException as error:
        original = error
        status.update(outcome="error",error_type=type(error).__name__,error=str(error),traceback=traceback.format_exc())
        raise
    finally:
        status.update(attempted_requests=budget.calls if budget else 0,wall_seconds=clock()-started)
        try:
            rd.transport.save(output/"status.json",status)
            commit()
        except BaseException as cleanup:
            if original is None:raise
            original.add_note(f"Saving stock evaluation status failed: {cleanup!r}")
    rd.transport.save(output/"completion.json",{str(p.relative_to(output)):mp.file_sha256(p)
        for p in output.rglob('*') if p.is_file()})
    commit()
    return report(output)


def analyze(entries,rows):
    mp._require_exact([r["case_id"] for r in rows],[c["case_id"] for c in entries],"stock analysis cases")
    indexed = {r["case_id"]:r for r in rows}
    assessments = []
    for c in entries:
        r = indexed[c["case_id"]]
        agrees = r["selected_destination"]==c["supported_destination"]
        supported_true = c["supported_destination"]==c["gold"]
        assessments.append(dict(r, family_id=c["family_id"],format=c["format"],probe=c["probe"],world=c["world"],
            supported_destination=c["supported_destination"],evidence_agrees=agrees,queried_evidence_true=supported_true,
            reader_error_on_correct_note=not r["correct"] and supported_true,
            writer_evidence_error=not supported_true,reader_evidence_error=not agrees))
    def cell(selected):
        n = len(selected)
        correct = sum(r["correct"] for r in selected)
        return dict(questions=n,correct=correct,accuracy=correct/n,
            evidence_agreement=sum(r["evidence_agrees"] for r in selected)/n,
            supported_true=sum(r["queried_evidence_true"] for r in selected),
            reader_errors_on_correct_notes=sum(r["reader_error_on_correct_note"] for r in selected),
            writer_evidence_errors=sum(r["writer_evidence_error"] for r in selected),
            reader_evidence_errors=sum(r["reader_evidence_error"] for r in selected))
    cells = {f"{fmt}/{probe}":cell([r for r in assessments if r["format"]==fmt and r["probe"]==probe])
             for fmt in mp.FORMATS for probe in mp.PROBES}
    per_family = {fid:{f"{fmt}/{probe}":cell([r for r in assessments if r["family_id"]==fid
        and r["format"]==fmt and r["probe"]==probe]) for fmt in mp.FORMATS for probe in mp.PROBES} for fid in FAMILIES}
    case_index = {c["case_id"]:c for c in entries}
    transitions = {}
    for fmt in mp.FORMATS:
        pairs = [(f"{fid}/{w}/{fmt}/256/P0",f"{fid}/{w}/{fmt}/256/P12") for fid in FAMILIES for w in range(4)]
        transitions[fmt] = dict(chains=len(pairs),
            changed_notes=sum(case_index[a]["notebook_sha256"]!=case_index[b]["notebook_sha256"] for a,b in pairs),
            correct_to_wrong=sum(indexed[a]["correct"] and not indexed[b]["correct"] for a,b in pairs),
            wrong_to_correct=sum(not indexed[a]["correct"] and indexed[b]["correct"] for a,b in pairs))
    return dict(cells=cells,per_family=per_family,assessments=assessments,transitions=transitions,
        json_minus_prose_accuracy={p:cells[f"json/{p}"]["accuracy"]-cells[f"prose/{p}"]["accuracy"] for p in mp.PROBES},
        limits="Four calibration families, B=256, queried facts only; descriptive development results, not held-out accuracy or a capacity/format superiority claim.")


def report(output):
    output = Path(output)
    manifest,entries = verify_package(output/"inputs")
    status = rd._read(output/"status.json")
    if status["manifest_sha256"]!=manifest["manifest_sha256"] or rd._read(output/"entry.json")["manifest"]!=manifest:
        raise ValueError("reported stock identity differs")
    model = rd._read(output/"model.json") if (output/"model.json").exists() else {}
    real = model.get("is_fake") is False
    preflight = rd._read(output/"tokenizer-preflight.json") if real else None
    expected_model = dict(model_id=mp.MODEL_ID,revision=mp.MODEL_REVISION,dtype="float16",
                          context_limit=8192,generation_seed=0,gpu=br.GPU)
    if real and (any(model.get(k)!=v for k,v in expected_model.items()) or manifest["writer_is_fake"]
                 or preflight["evidence"]!="actual_cached_tokenizer"
                 or set(preflight["prompts"])!={c["prompt_sha256"] for c in entries}):
        raise ValueError("real stock GPU/writer/tokenizer evidence differs")
    rows,events,results,completed = [],[],{},[]
    for fid in FAMILIES:
        directory = output/fid
        if (directory/"events.jsonl").exists():events += rd._rows(directory/"events.jsonl")
        if (directory/"completion.json").exists():
            rr,got = br.audit_unit(directory,[(c,"restricted") for c in entries if c["family_id"]==fid],model,preflight)
            rows += rr;results.update(got);completed.append(fid)
    if (output/"checks/events.jsonl").exists():events += rd._rows(output/"checks/events.jsonl")
    agreement = None
    if status["complete"]:
        ledger = rd._read(output/"completion.json")
        mp._require_exact(list(ledger),[str(p.relative_to(output)) for p in output.rglob('*')
            if p.is_file() and p!=output/"completion.json"],"stock result files")
        if any(mp.file_sha256(output/name)!=expected for name,expected in ledger.items()):
            raise ValueError("stock result completion bytes differ")
        if (completed!=list(FAMILIES) or status["completed_families"]!=completed
                or status["attempted_requests"]!=REQUEST_CEILING
                or status["model_is_fake"]!= (not real) or status["reference_is_fake"]!= (not real)):
            raise ValueError("complete stock coverage/real identity differs")
        specs = [(c,"reference") for c in entries]+[(c,"repeat") for c in entries]
        _,checks = br.audit_unit(output/"checks",specs,model,preflight)
        agreement = []
        for c in entries:
            a,b,r = results[c["case_id"],"restricted"],checks[c["case_id"],"reference"],checks[c["case_id"],"repeat"]
            if not rd.compare_scores(a,b):raise ValueError("completed independent scoring mismatch")
            agreement.append(dict(case_id=c["case_id"],repeat_label_agrees=a.text==r.text,
                repeat_logits_agree=rd.compare_scores(a,r),
                max_reference_difference=max(abs(x-y) for x,y in zip(a.metadata["candidate_logits"],b.metadata["candidate_logits"]))))
    requests = [e for e in events if e["event"]=="model_request"]
    responses = [e for e in events if e["event"]=="model_response"]
    if status["complete"] and (len(requests)!=REQUEST_CEILING or len(responses)!=REQUEST_CEILING):
        raise ValueError("stock physical request coverage differs")
    return dict(status=status,primary_assessments=len(rows),completed_family_count=len(completed),checks=agreement,
        analysis=analyze(entries,rows) if status["complete"] else None,
        known_usage=dict(requests=len(requests),responses=len(responses),unknown_usage_requests=len(requests)-len(responses),
            calls_by_method={m:sum(r["method"]==m for r in requests) for m in ("restricted","reference","repeat")},
            input_tokens=sum(r["input_tokens"] for r in responses),output_tokens=sum(r["output_tokens"] for r in responses),
            forward_seconds=sum(r["elapsed_seconds"] for r in responses)),
        usage_scope="New reader scoring only; the copied writer provenance contains earlier calls, not new inference.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command",required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--corpus",type=Path,required=True);prep.add_argument("--annotations",type=Path,required=True)
    prep.add_argument("--output-dir",type=Path,required=True)
    execute = sub.add_parser("run")
    execute.add_argument("--package",type=Path,required=True);execute.add_argument("--output-dir",type=Path,required=True)
    show = sub.add_parser("report");show.add_argument("directory",type=Path)
    args = parser.parse_args()
    result = (prepare(args.corpus,args.annotations,args.output_dir) if args.command=="prepare"
              else run(args.package,args.output_dir) if args.command=="run" else report(args.directory))
    print(json.dumps(result,indent=1,sort_keys=True))


if __name__=="__main__":
    main()
