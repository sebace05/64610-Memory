"""Frozen paired 160-family reader base-rate study; optional imports are GPU-bound."""
import argparse
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import random
import shutil
import time
import traceback
import zipfile

from . import memory_probe as mp
from . import reader_diagnostic as rd
from . import writer_collection as wc
from .components import Generation
from .runner import _LoggedModel

VERSION = "reader-base-rate-v1"
N = 160
ARMS = ("opaque", "numbered")
GPU = "NVIDIA A10"
MARGIN = 0.02
LOW_ERROR = 0.01
SENTINELS = ("F000", "F001", "F080", "F081")
REQUEST_CEILING = 2608  # 2560 primary + 16 contemporaneous checks + 16 reference + 16 repeats
SOFT_SECONDS = 1500
SOURCE_FILES = tuple(dict.fromkeys((*wc.SOURCE_FILES, *rd.SOURCE_FILES,
    "game_memory/reader_base_rate.py", "tests/test_reader_base_rate.py", "docs/reader-base-rate-v1.md")))


def stream(*purpose):
    key = "|".join((VERSION, "0", *map(str, purpose)))
    return random.Random(int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big"))


def families():
    # Read held-out structure only for software disjointness; do not print or infer on it.
    previous = {**{f"legacy/{k}": v for k, v in mp.generate_splits().items()},
                **{f"matched/{k}": v for k, v in wc.generate_splits().items()}}
    used = {n for fs in previous.values() for f in fs for n in [*f["order"], *f["pulses"]]}
    used.update(("balok", "zomip"))
    excluded = {mp._composition(f) for fs in previous.values() for f in fs}
    olds = list(mp.DESTINATIONS)
    stream("old-values").shuffle(olds)
    numbers = stream("numbered-identifiers").sample(range(1000, 10000), N * 8)
    result = []
    for i in range(N):
        old = olds[(i // 2) % 4] if i % 2 == 0 else None
        for attempt in range(100):
            trial = set(used)
            f = wc._build_family(stream(i, "family", attempt), stream(i, "options"),
                                f"F{i:03d}", "development", i, old, trial, attempt)
            if mp._composition(f) not in excluded:
                used = trial
                break
        else:
            raise ValueError("fresh family generation exhausted")
        f["numbered_names"] = dict(zip(f["order"], (f"item-{x:04d}" for x in numbers[8*i:8*i+8])))
        result.append(f)
    # As in v1, repeated normalized compositions within this development split are allowed.
    mp.check_splits({**previous, "base-rate-development": result})
    return result


def cases(fs):
    result = []
    for f in fs:
        for world in f["worlds"]:
            reduced = mp.public_state(world["observations"])
            for arm in ARMS:
                mapping = ({n: n for n in f["order"]} if arm == "opaque" else f["numbered_names"])
                state = {mapping[n]: reduced["state"][n] for n in f["order"]}
                query = mapping[f["roles"]["target"]]
                for fmt in mp.FORMATS:
                    note = (mp.prose_note(dict(order=list(state), state=state)) if fmt == "prose"
                            else json.dumps(state, ensure_ascii=False, separators=(",", ":")))
                    messages = [asdict(m) for m in mp.reader_messages(note, query, f["options"])]
                    result.append(dict(case_id=f"{f['family_id']}/{world['world']}/{arm}/{fmt}",
                        family_id=f["family_id"], query_type=f["query_type"], world=world["world"],
                        arm=arm, format=fmt, query=query, gold=world["answer"], options=f["options"],
                        entity_order=list(state), state=state, memory=note, messages=messages,
                        prompt_sha256=mp.digest(messages)))
    return result


def sentinels(entries):
    return [c for c in entries if c["family_id"] in SENTINELS and c["world"] == 0]


def settings():
    return dict(version=VERSION, families=N, arms=list(ARMS), gpu=GPU, global_seed=0,
        primary_forwards=N*16, request_ceiling=REQUEST_CEILING, soft_seconds=SOFT_SECONDS,
        execution_seconds=1800, practical_margin=MARGIN, low_observed_error=LOW_ERROR,
        bootstrap_samples=10000, bootstrap_seed=0,
        model=dict(id=mp.MODEL_ID, revision=mp.MODEL_REVISION, dtype="float16", context_limit=8192, seed=0))


def prepare(output):
    fs = families()
    entries = cases(fs)
    if len({c["prompt_sha256"] for c in entries}) != N*16:
        raise ValueError("primary prompts are not unique")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    rd.transport.save(output/"families.json", fs)
    rd.transport.save(output/"cases.json", entries)
    source = Path(__file__).resolve().parents[1]
    with zipfile.ZipFile(output/"source.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in SOURCE_FILES:
            archive.write(source/name, name)
    manifest = dict(**settings(), files={n: mp.file_sha256(output/n)
        for n in ("families.json", "cases.json", "source.zip")},
        source_files={n: mp.file_sha256(source/n) for n in SOURCE_FILES})
    manifest["manifest_sha256"] = mp.digest(manifest)
    rd.transport.save(output/"manifest.json", manifest)
    return manifest


def verify_package(package, source=None):
    package = Path(package)
    manifest = rd._read(package/"manifest.json")
    if manifest["manifest_sha256"] != mp.digest({k: v for k, v in manifest.items() if k != "manifest_sha256"}):
        raise ValueError("base-rate manifest differs")
    if any(manifest.get(k) != v for k, v in settings().items()):
        raise ValueError("fixed base-rate settings differ")
    if set(manifest["files"]) != {"families.json", "cases.json", "source.zip"}:
        raise ValueError("base-rate package inventory differs")
    for name, expected in manifest["files"].items():
        if mp.file_sha256(package/name) != expected:
            raise ValueError("base-rate package bytes differ")
    with zipfile.ZipFile(package/"source.zip") as archive:
        if sorted(archive.namelist()) != sorted(SOURCE_FILES) or set(manifest["source_files"]) != set(SOURCE_FILES):
            raise ValueError("base-rate source inventory differs")
        for name, expected in manifest["source_files"].items():
            if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                raise ValueError("archived base-rate source differs")
            if source is not None and mp.file_sha256(Path(source)/name) != expected:
                raise ValueError("current base-rate source differs: " + name)
    fs, entries = rd._read(package/"families.json"), rd._read(package/"cases.json")
    if fs != families() or entries != cases(fs):
        raise ValueError("base-rate families/cases differ from frozen construction")
    return manifest, fs, entries


def load_models(manifest, entries, output):
    from . import transformers_model as tm
    os.environ.update(rd.transport.ENV)
    config = tm.TransformersConfig(revision=mp.MODEL_REVISION, dtype="float16", device="cuda",
        context_limit=8192, action_max_new_tokens=32, memory_max_new_tokens=1024,
        generation_seed=0, local_files_only=True)
    cache = Path("/cache/huggingface/hub/models--Qwen--Qwen3-4B-Instruct-2507/snapshots")/mp.MODEL_REVISION
    runtime, cfg = rd.transport.runtime_and_cache(tm, config, cache)
    rd.transport.save(output/"runtime-cache.json", runtime)
    if runtime["runtime"]["gpu"] != GPU:
        raise ValueError("pinned NVIDIA A10 required; refused before weights")
    tokenizer = rd.transport.cached_tokenizer(cache)
    checked = rd.preflight(entries, tokenizer, cfg["vocab_size"], evidence="actual_cached_tokenizer")
    rd.transport.save(output/"tokenizer-preflight.json", checked)
    if len(checked["prompts"]) != N*16:
        raise ValueError("actual preflight coverage differs")
    names = sorted({n for c in entries for n in c["entity_order"]})
    rd.transport.save(output/"name-tokens.json", dict(evidence="actual_cached_tokenizer", names={
        n: {label: dict(ids=(ids := tokenizer.encode(text, add_special_tokens=False)),
                       pieces=tokenizer.convert_ids_to_tokens(ids))
            for label, text in dict(bare=n, space=" "+n, json_key='"'+n+'":').items()}
        for n in names}))
    model = tm.TransformersModel(config)
    rd.transport.save(output/"model.json", model.metadata)
    return model, rd.ReferenceModel(model)


class _Budget:
    def __init__(self, deadline, clock, limit):
        self.deadline, self.clock, self.limit, self.calls = deadline, clock, limit, 0

    def check(self):
        if self.clock() >= self.deadline:
            raise TimeoutError("base-rate deadline before forward")
        if self.calls >= self.limit:
            raise RuntimeError("base-rate request ceiling")
        self.calls += 1


class _Reader:
    def __init__(self, model, budget):
        self.model, self.budget = model, budget

    @property
    def metadata(self):
        return self.model.metadata

    def score_choices(self, messages, *, labels):
        self.budget.check()
        return self.model.score_choices(messages, labels=labels)

    def generate(self, *args, **kwargs):
        raise ValueError("base-rate study forbids generation/writing")


def _result(response):
    return Generation(**{k: response[k] for k in ("text", "input_tokens", "output_tokens", "elapsed_seconds", "metadata")})


def _score(unit, logged, case, method):
    unit.context = dict(step=0, role="reader", case_id=case["case_id"], method=method)
    result = logged.score_choices(rd._messages(case), labels=mp.LABELS)
    destination = case["options"][mp.LABELS.index(result.text)]
    mp._write_line(unit.files["assessments.jsonl"], dict(case_id=case["case_id"], method=method,
        source_request_id=unit.request_id, query=case["query"], gold=case["gold"],
        selected_letter=result.text, selected_destination=destination, correct=destination == case["gold"],
        prompt_sha256=case["prompt_sha256"]))
    return result


def audit_unit(directory, specs, model_metadata, preflight=None):
    directory = Path(directory)
    ledger = mp.verify_completion(directory)
    mp._require_exact(list(ledger["files"]), ["events.jsonl", "writes.jsonl", "assessments.jsonl", "summary.json"], "base-rate unit files")
    if rd._rows(directory/"writes.jsonl"):
        raise ValueError("writer records in scoring-only unit")
    events, rows = rd._rows(directory/"events.jsonl"), rd._rows(directory/"assessments.jsonl")
    requests = {e["request_id"]: e for e in events if e["event"] == "model_request"}
    responses = {e["request_id"]: e for e in events if e["event"] == "model_response"}
    if (len(requests) != len(specs) or len(responses) != len(specs) or len(events) != 2*len(specs)
            or sorted(requests) != list(range(len(specs))) or set(requests) != set(responses)):
        raise ValueError("base-rate request/response coverage differs")
    expected = {(c["case_id"], method): (i, c) for i, (c, method) in enumerate(specs)}
    mp._require_exact([(r["case_id"], r["method"]) for r in rows], list(expected), "base-rate assessment coverage")
    summary = rd._read(directory/"summary.json")
    if summary["model_identity"] != mp.digest(model_metadata) or summary["requests"] != len(specs):
        raise ValueError("unit model identity/accounting differs")
    real = model_metadata.get("is_fake") is False
    for row in rows:
        rid, c = expected[row["case_id"], row["method"]]
        request, response = requests[rid], responses[rid]
        logits = response["metadata"]["candidate_logits"]
        label = rd.reference_argmax(logits)
        destination = c["options"][mp.LABELS.index(label)]
        if (row["source_request_id"] != rid or request["case_id"] != c["case_id"]
                or request["method"] != row["method"] or request["purpose"] != "action"
                or request["messages"] != c["messages"] or response["text"] != label
                or row["selected_letter"] != label or row["selected_destination"] != destination
                or row["query"] != c["query"] or row["gold"] != c["gold"]
                or row["prompt_sha256"] != c["prompt_sha256"] or row["correct"] != (destination == c["gold"])):
            raise ValueError("base-rate decision differs from raw frozen prompt/logits")
        if real:
            evidence = "independent_raw_forward" if row["method"] == "reference" else "actual_model_forward"
            meta, checked = response["metadata"], preflight["prompts"][c["prompt_sha256"]]
            if (meta.get("scoring_evidence") != evidence or response["output_tokens"] != 1
                    or response["input_tokens"] != checked["input_tokens"]
                    or meta["label_token_ids"] != checked["label_token_ids"]
                    or meta["rendered_prompt_sha256"] != checked["rendered_prompt_sha256"]):
                raise ValueError("actual forward/tokenizer evidence differs")
    return rows, {(row["case_id"], row["method"]): _result(responses[row["source_request_id"]]) for row in rows}


def _reuse_units(reuse, manifest, by_family):
    validated = {}
    for item in reuse:
        fid, directory = item["family_id"], Path(item["directory"])
        if fid not in by_family or fid in validated:
            raise ValueError("unknown/duplicate reused development family")
        origin = rd._read(directory.parent/"entry.json")["manifest"]
        if (origin != manifest or item["manifest_sha256"] != manifest["manifest_sha256"]
                or mp.file_sha256(directory/"completion.json") != item["completion_sha256"]):
            raise ValueError("reused package/unit identity differs")
        source_model = rd._read(directory.parent/"model.json")
        preflight = rd._read(directory.parent/"tokenizer-preflight.json") if source_model.get("is_fake") is False else None
        audit_unit(directory, [(c, "restricted") for c in by_family[fid]], source_model, preflight)
        validated[fid] = dict(item, source_model=source_model)
    return validated


def run(package, output, *, loader=load_models, commit=lambda: None, clock=time.monotonic, reuse=()):
    manifest, fs, entries = verify_package(package, Path(__file__).resolve().parents[1])
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    started = clock()
    deadline = started+SOFT_SECONDS
    rd.transport.save(output/"entry.json", dict(manifest=manifest))
    shutil.copyfile(Path(package)/"cases.json", output/"cases.json")
    shutil.copyfile(Path(package)/"families.json", output/"families.json")
    commit()
    by_family = {f["family_id"]: [c for c in entries if c["family_id"] == f["family_id"]] for f in fs}
    status = dict(complete=False, completed_families=[], manifest_sha256=manifest["manifest_sha256"], reused_requests=0)
    budget, original = None, None
    try:
        reused = _reuse_units(reuse, manifest, by_family)
        rd.transport.save(output/"reuse.json", list(reused.values()))
        model, reference = loader(manifest, entries, output)
        status.update(model_is_fake=model.metadata.get("is_fake") is not False,
                      reference_is_fake=reference.metadata.get("is_fake") is not False)
        if not status["model_is_fake"] and model.metadata.get("gpu") != GPU:
            raise ValueError("unpinned GPU")
        if not (output/"model.json").exists():
            rd.transport.save(output/"model.json", model.metadata)
        budget = _Budget(deadline, clock, REQUEST_CEILING-16*len(reused))
        primary, other = _Reader(model, budget), _Reader(reference, budget)
        for family in fs:
            fid = family["family_id"]
            selected = by_family[fid]
            if fid in reused:
                item = reused[fid]
                keys = ("is_fake", "gpu", "model_id", "revision", "dtype", "context_limit", "generation_seed", *rd.transport.RUNTIME)
                if any(item["source_model"].get(k) != model.metadata.get(k) for k in keys):
                    raise ValueError("reused/new model runtime differs")
                shutil.copytree(item["directory"], output/fid)
                audit_unit(output/fid, [(c, "restricted") for c in selected],
                    item["source_model"], rd._read(output/"tokenizer-preflight.json") if not status["model_is_fake"] else None)
                status["reused_requests"] += 16
                commit()
            else:
                unit = mp._Unit(output/fid, primary, deadline, clock)
                try:
                    for c in selected:
                        _score(unit, unit.logged, c, "restricted")
                    unit.complete(dict(requests=unit.request_id+1, model_identity=mp.digest(model.metadata)), commit)
                finally:
                    unit.close()
            status["completed_families"].append(fid)
        selected = sentinels(entries)
        unit = mp._Unit(output/"checks", primary, deadline, clock)
        controls = {}
        reference_log = _LoggedModel(other, unit._emit, lambda: 0)
        try:
            for c in selected:
                controls[c["case_id"]] = _score(unit, unit.logged, c, "restricted_check")
                checked = _score(unit, reference_log, c, "reference")
                if not rd.compare_scores(controls[c["case_id"]], checked):
                    raise ValueError("independent scoring mismatch; inspect raw evidence")
            for c in selected:
                _score(unit, unit.logged, c, "repeat")
            unit.complete(dict(requests=unit.request_id+1, model_identity=mp.digest(model.metadata)), commit)
        finally:
            unit.close()
        status.update(complete=True, outcome="base_rate_complete")
    except BaseException as error:
        original = error
        status.update(outcome="error", error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc())
        raise
    finally:
        status.update(new_attempted_requests=budget.calls if budget else 0, wall_seconds=clock()-started)
        try:
            rd.transport.save(output/"status.json", status)
            commit()
        except BaseException as cleanup:
            if original is None:
                raise
            original.add_note(f"Saving base-rate status also failed: {cleanup!r}")
    rd.transport.save(output/"completion.json", {str(p.relative_to(output)):mp.file_sha256(p)
        for p in output.rglob('*') if p.is_file()})
    commit()
    return report(output)


def wilson(successes, total):
    z = 1.959963984540054
    p = successes/total
    scale = 1+z*z/total
    mid = (p+z*z/(2*total))/scale
    half = z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/scale
    return [max(0, mid-half), min(1, mid+half)]


def estimate(updated, untouched):
    interval = mp.bootstrap(updated, untouched, samples=10000, seed=0)
    values = updated+untouched
    return dict(value=sum(values)/len(values), ci95=[interval["lower_2_5"], interval["upper_97_5"]],
                degenerate=min(values)==max(values))


def decide(cells, effects):
    if all(c["error_rate"]["value"] <= LOW_ERROR for c in cells.values()):
        return dict(naming="no redesign justified by observed rates", adaptation="stock reader first; little observed headroom",
                    result="low_observed_error", note="This is an empirical planning rule, not proof of a sub-1% population error rate.")
    pooled = effects["pooled"]
    if pooled["ci95"][0] > MARGIN and all(effects[f]["value"] >= 0 for f in mp.FORMATS):
        return dict(result="alternative_materially_better", naming="candidate numbered-ID protocol; recheck writer outputs/sizes",
                    adaptation="assess residual reader errors before deciding on LoRA")
    if pooled["ci95"][1] < -MARGIN:
        return dict(result="alternative_materially_worse", naming="retain current generator; reject this numbered-ID alternative",
                    adaptation="assess residual errors under current names before deciding on LoRA")
    if all(not effects[k]["degenerate"] and -MARGIN <= effects[k]["ci95"][0]
           and effects[k]["ci95"][1] <= MARGIN for k in ("pooled", *mp.FORMATS)):
        return dict(result="practically_similar", naming="retain current generator",
                    adaptation="consider reader LoRA if residual reader errors remain meaningful")
    return dict(result="inconclusive", naming="retain frozen generator pending stronger evidence",
                adaptation="do not infer equivalence or automatically fine-tune from an inconclusive naming comparison")


def analyze(fs, entries, rows):
    mp._require_exact([r["case_id"] for r in rows], [c["case_id"] for c in entries], "base-rate analysis cases")
    indexed = {r["case_id"]: r for r in rows}
    per_family = []
    for f in fs:
        fid = f["family_id"]
        counts = {f"{arm}/{fmt}": sum(not indexed[f"{fid}/{w}/{arm}/{fmt}"]["correct"] for w in range(4))
                  for arm in ARMS for fmt in mp.FORMATS}
        per_family.append(dict(family_id=fid, query_type=f["query_type"], errors=counts))
    def metric(values):
        return estimate([v for f,v in zip(fs,values) if f["query_type"] == "updated"],
                        [v for f,v in zip(fs,values) if f["query_type"] == "untouched"])
    cells = {}
    for arm in ARMS:
        for fmt in mp.FORMATS:
            key = f"{arm}/{fmt}"
            counts = [f["errors"][key] for f in per_family]
            affected = sum(n > 0 for n in counts)
            cells[key] = dict(errors=sum(counts), questions=N*4, accuracy=1-sum(counts)/(N*4), error_rate=metric([n/4 for n in counts]),
                affected_families=affected, families=N, family_error_rate=affected/N,
                family_error_wilson95=wilson(affected, N))
    differences = {fmt: [(f["errors"][f"opaque/{fmt}"]-f["errors"][f"numbered/{fmt}"])/4 for f in per_family]
                   for fmt in mp.FORMATS}
    effects = {fmt: metric(values) for fmt,values in differences.items()}
    effects["pooled"] = metric([(a+b)/2 for a,b in zip(differences["prose"], differences["json"])])
    gaps = {arm:metric([(f["errors"][f"{arm}/prose"]-f["errors"][f"{arm}/json"])/4 for f in per_family]) for arm in ARMS}
    strata = {kind:{key:dict(errors=sum(f["errors"][key] for f in per_family if f["query_type"]==kind),
                       questions=80*4, affected_families=sum(f["errors"][key]>0 for f in per_family if f["query_type"]==kind))
                    for key in cells} for kind in ("updated","untouched")}
    return dict(cells=cells, effects=effects, json_minus_prose_accuracy=gaps, per_family=per_family,
                decision=decide(cells, effects), practical_margin=MARGIN, query_type_counts=strata,
                uncertainty="10000 paired family bootstrap resamples, stratified 80/80 by query type, seed 0. Degenerate intervals do not establish equivalence; Wilson intervals summarize affected-family rates.")


def report(output):
    output = Path(output)
    status = rd._read(output/"status.json")
    manifest = rd._read(output/"entry.json")["manifest"]
    if (manifest["manifest_sha256"] != status["manifest_sha256"]
            or manifest["manifest_sha256"] != mp.digest({k:v for k,v in manifest.items() if k!="manifest_sha256"})
            or any(manifest.get(k)!=v for k,v in settings().items())):
        raise ValueError("reported base-rate identity/settings differ")
    for name in ("families.json", "cases.json"):
        if mp.file_sha256(output/name) != manifest["files"][name]:
            raise ValueError("result input bytes differ")
    fs, entries = rd._read(output/"families.json"), rd._read(output/"cases.json")
    if fs != families() or entries != cases(fs):
        raise ValueError("reported inputs differ from fixed development construction")
    model = rd._read(output/"model.json") if (output/"model.json").exists() else {}
    if model.get("is_fake") is False and model.get("gpu") != GPU:
        raise ValueError("result GPU differs")
    preflight = rd._read(output/"tokenizer-preflight.json") if model.get("is_fake") is False else None
    if preflight is not None and (preflight["evidence"]!="actual_cached_tokenizer" or len(preflight["prompts"])!=N*16):
        raise ValueError("actual preflight evidence/coverage differs")
    reuse = rd._read(output/"reuse.json") if (output/"reuse.json").exists() else []
    reused = {r["family_id"]:r for r in reuse}
    if len(reused)!=len(reuse) or not set(reused)<={f["family_id"] for f in fs}:
        raise ValueError("reused family inventory differs")
    rows, events, results = [], [], {}
    completed = []
    for f in fs:
        fid, directory = f["family_id"], output/f["family_id"]
        if (directory/"events.jsonl").exists():
            events += rd._rows(directory/"events.jsonl")
        if (directory/"completion.json").exists():
            if fid in reused and mp.file_sha256(directory/"completion.json") != reused[fid]["completion_sha256"]:
                raise ValueError("copied unit differs from pinned original")
            selected = [c for c in entries if c["family_id"] == fid]
            rr, got = audit_unit(directory, [(c,"restricted") for c in selected],
                                 reused[fid]["source_model"] if fid in reused else model, preflight)
            rows += rr; results.update(got); completed.append(fid)
    checks, agreement = None, None
    if (output/"checks/events.jsonl").exists():
        events += rd._rows(output/"checks/events.jsonl")
    if status["complete"]:
        if status["model_is_fake"] != (model.get("is_fake") is not False) or status["reused_requests"]!=16*len(reused):
            raise ValueError("real/reused corpus identity differs")
        ledger = rd._read(output/"completion.json")
        mp._require_exact(list(ledger), [str(p.relative_to(output)) for p in output.rglob('*')
            if p.is_file() and p != output/"completion.json"], "base-rate completion files")
        for name, expected in ledger.items():
            if mp.file_sha256(output/name) != expected:
                raise ValueError("base-rate completion hash differs")
        if completed != [f["family_id"] for f in fs] or completed != status["completed_families"]:
            raise ValueError("incomplete base-rate family coverage")
        sentinel = sentinels(entries)
        specs = [(c,m) for c in sentinel for m in ("restricted_check","reference")] + [(c,"repeat") for c in sentinel]
        _, checks = audit_unit(output/"checks", specs, model, preflight)
        agreement = []
        for c in sentinel:
            a,b,r = (checks[c["case_id"], m] for m in ("restricted_check","reference","repeat"))
            if not rd.compare_scores(a,b):
                raise ValueError("completed independent scoring mismatch")
            agreement.append(dict(case_id=c["case_id"], repeat_label_agrees=a.text == r.text,
                repeat_logits_agree=rd.compare_scores(a,r), corpus_replay_label_agrees=results[c["case_id"],"restricted"].text == a.text,
                max_reference_difference=max(abs(x-y) for x,y in zip(a.metadata["candidate_logits"],b.metadata["candidate_logits"]))))
        if status["new_attempted_requests"] + status["reused_requests"] != REQUEST_CEILING:
            raise ValueError("new/reused physical-call accounting differs")
    responses = [e for e in events if e["event"] == "model_response"]
    requests = [e for e in events if e["event"] == "model_request"]
    if status["complete"] and (len(requests) != REQUEST_CEILING or len(responses) != REQUEST_CEILING):
        raise ValueError("global physical-call coverage differs")
    return dict(status=status, completed_family_count=len(completed), primary_assessments=len(rows),
        analysis=analyze(fs,entries,rows) if status["complete"] else None, checks=agreement,
        known_usage=dict(requests=len(requests), responses=len(responses), unknown_usage_requests=len(requests)-len(responses),
            calls_by_method={m:sum(e["method"]==m for e in requests) for m in ("restricted","restricted_check","reference","repeat")},
            input_tokens=sum(e["input_tokens"] for e in responses), output_tokens=sum(e["output_tokens"] for e in responses),
            forward_seconds=sum(e["elapsed_seconds"] for e in responses)),
        limits="Controlled sufficient-note reader study under one frozen synthetic development generator; no writer performance, 8B comparison, training result, or general model-wide error rate.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare"); prep.add_argument("--output-dir", type=Path, required=True)
    execute = sub.add_parser("run")
    execute.add_argument("--package", type=Path, required=True); execute.add_argument("--output-dir", type=Path, required=True)
    execute.add_argument("--reuse-plan", type=Path)
    show = sub.add_parser("report"); show.add_argument("directory", type=Path)
    args = parser.parse_args()
    result = (prepare(args.output_dir) if args.command == "prepare" else report(args.directory) if args.command == "report"
              else run(args.package,args.output_dir,reuse=rd._read(args.reuse_plan) if args.reuse_plan else ()))
    print(json.dumps(result,indent=1,sort_keys=True))


if __name__ == "__main__":
    main()
