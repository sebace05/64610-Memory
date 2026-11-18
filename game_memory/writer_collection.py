"""Writer-only collection for the matched reader-training checkpoint.

Preparation is offline. The calibration entrypoint writes C00-C03 only, using
the unchanged probe writers/chain runner/auditor; it never invokes a reader.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import time
import traceback
import zipfile

from . import memory_probe as mp
from . import memory_probe_modal as transport

PROTOCOL = "matched-reader-training-v1"
VERSION = "writer-collection-v1.1"
SPLITS = {"calibration": ("C", 4), "training": ("R", 32),
          "validation": ("V", 8), "test": ("E", 16)}
ALLOWANCE = 256
REQUEST_CEILING = 896  # 4 families * 4 worlds * 2 formats * 14 writes * (primary + repair)
SOFT_SECONDS = 6900
SOURCE_FILES = (*mp.SOURCE_FILES, "game_memory/memory_probe_modal.py",
                "game_memory/writer_collection.py", "tests/test_writer_collection.py",
                "tests/test_memory_probe.py", "docs/writer-collection-v1.md",
                "docs/matched-reader-training-v1.md")
# mp.SOURCE_FILES already contains test_memory_probe.py.
SOURCE_FILES = tuple(dict.fromkeys(SOURCE_FILES))


def stream(*purpose):
    key = "|".join((PROTOCOL, "0", *map(str, purpose)))
    return random.Random(int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big"))


def _build_family(rng, options_rng, family_id, split, index, old_value, used, attempt):
    """Same v1 construction, with explicit RNGs instead of mutating v1 globals."""
    names = [mp._name(rng, used) for _ in range(8)]
    order = names[:]
    rng.shuffle(order)
    base = {n: rng.choice(mp.DESTINATIONS) for n in names}
    target, revoked = names[0], names[2]
    updated = target if index % 2 == 0 else names[1]
    if index % 2 == 0:
        base[target] = old_value
    update_value = None if index % 2 == 0 else rng.choice(mp.DESTINATIONS)
    pulses = [mp._name(rng, used) for _ in range(mp.FILLERS)]
    options = [*mp.DESTINATIONS, mp.ABSTAIN]
    options_rng.shuffle(options)
    worlds = []
    for w, answer in enumerate(mp.DESTINATIONS):
        initial = dict(base)
        if index % 2:
            initial[target] = answer
        value = answer if index % 2 == 0 else update_value
        obs0 = "Assignments: " + "; ".join(f"{n}={initial[n]}" for n in order) + "."
        obs1 = (f"Update: {updated} is now assigned to {value}, replacing its previous "
                f"assignment.\n{revoked.capitalize()}'s assignment is revoked; its destination "
                "is now unknown.")
        fillers = [f"Ambient pulse {p}. No assignments changed." for p in pulses]
        worlds.append({"world": w, "answer": answer, "initial": initial, "update_value": value,
                       "observations": [obs0, obs1, *fillers]})
    return {"family_id": family_id, "split": split, "index": index,
            "query_type": "updated" if index % 2 == 0 else "untouched", "order": order,
            "base": base, "roles": {"target": target, "updated": updated, "revoked": revoked},
            "options": options, "labels": list(mp.LABELS), "pulses": pulses, "worlds": worlds,
            "generation_attempt": attempt}


def generate_splits():
    """Freeze all 60 fresh families; no names/compositions cross new or legacy splits."""
    legacy = mp.generate_splits()
    used = {n for fs in legacy.values() for f in fs for n in [*f["order"], *f["pulses"]]}
    compositions = {mp._composition(f) for fs in legacy.values() for f in fs}
    splits = {}
    for split, (prefix, count) in SPLITS.items():
        olds = list(mp.DESTINATIONS)
        stream(split, "old-values").shuffle(olds)
        families = []
        for index in range(count):
            old = olds[(index // 2) % 4] if index % 2 == 0 else None
            for attempt in range(100):
                trial_used = set(used)
                family = _build_family(stream(split, index, "family", attempt),
                    stream(split, index, "options"), f"{prefix}{index:02d}", split,
                    index, old, trial_used, attempt)
                composition = mp._composition(family)
                if composition not in compositions:
                    used = trial_used
                    compositions.add(composition)
                    families.append(family)
                    break
            else:
                raise RuntimeError("fresh disjoint family generation exhausted")
        splits[split] = families
    check_splits(splits)
    return splits


def check_splits(splits):
    if set(splits) != set(SPLITS):
        raise ValueError("split allocation differs")
    for split, (prefix, count) in SPLITS.items():
        if [f["family_id"] for f in splits[split]] != [f"{prefix}{i:02d}" for i in range(count)]:
            raise ValueError("family allocation/order differs")
        for i, family in enumerate(splits[split]):
            if (family["split"] != split or family["index"] != i
                    or family["query_type"] != ("updated" if i % 2 == 0 else "untouched")
                    or [w["world"] for w in family["worlds"]] != list(range(4))):
                raise ValueError("family split/stratum/world allocation differs")
    mp.check_splits({**{f"legacy/{s}": fs for s, fs in mp.generate_splits().items()}, **splits})


def _read(path):
    return json.loads(Path(path).read_text())


def _rows(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines()]


def prepare(output, source=None):
    """Offline split/source freeze. CLI output contains hashes/IDs, never test facts."""
    source = Path(source or Path(__file__).resolve().parents[1])
    splits = generate_splits()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "splits").mkdir()
    info = {}
    for split, families in splits.items():
        name = f"splits/{split}.json"
        transport.save(output / name, families)
        info[split] = {"path": name, "sha256": mp.file_sha256(output / name),
                       "family_ids": [f["family_id"] for f in families]}
    with zipfile.ZipFile(output / "source.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in SOURCE_FILES:
            archive.write(source / name, name)
    manifest = {"version": VERSION, "protocol": PROTOCOL, "global_seed": 0,
        "splits": info, "calibration_allowance": ALLOWANCE,
        "budget_rule": "128 if all 64 recounted P0/P12 snapshots fit 128; otherwise 256",
        "request_ceiling": REQUEST_CEILING, "primary_writes": 448, "snapshot_count": 64,
        "soft_seconds": SOFT_SECONDS, "execution_seconds": 7200,
        "writer_version": mp.WRITER_VERSION, "reader_version": mp.READER_VERSION,
        "writer_component_origin": mp.PROTOCOL, "generation_cap": 1024,
        "model": {"id": mp.MODEL_ID, "revision": mp.MODEL_REVISION, "device": "cuda",
                  "dtype": "float16", "context_limit": 8192, "generation_seed": 0},
        "legacy_split_digest": mp.digest(mp.generate_splits()),
        "source_zip_sha256": mp.file_sha256(output / "source.zip"),
        "source_files": {n: mp.file_sha256(source / n) for n in SOURCE_FILES}}
    manifest["manifest_sha256"] = mp.digest(manifest)
    transport.save(output / "manifest.json", manifest)
    return manifest


def verify_package(package, source=None):
    package = Path(package)
    manifest = _read(package / "manifest.json")
    if manifest["manifest_sha256"] != mp.digest({k: v for k, v in manifest.items()
                                                if k != "manifest_sha256"}):
        raise ValueError("writer manifest hash differs")
    if (manifest["version"] != VERSION or manifest["protocol"] != PROTOCOL
            or manifest["calibration_allowance"] != ALLOWANCE
            or manifest["request_ceiling"] != REQUEST_CEILING
            or manifest["soft_seconds"] != SOFT_SECONDS
            or manifest["primary_writes"] != 448 or manifest["snapshot_count"] != 64
            or set(manifest["source_files"]) != set(SOURCE_FILES)
            or set(manifest["splits"]) != set(SPLITS)):
        raise ValueError("writer collection settings differ")
    for split, (prefix, count) in SPLITS.items():
        item = manifest["splits"][split]
        if (item["path"] != f"splits/{split}.json"
                or item["family_ids"] != [f"{prefix}{i:02d}" for i in range(count)]):
            raise ValueError("sealed split allocation differs")
        if mp.file_sha256(package / item["path"]) != item["sha256"]:
            raise ValueError("sealed split bytes differ")
    if mp.file_sha256(package / "source.zip") != manifest["source_zip_sha256"]:
        raise ValueError("writer source archive differs")
    with zipfile.ZipFile(package / "source.zip") as archive:
        if sorted(archive.namelist()) != sorted(manifest["source_files"]):
            raise ValueError("writer source inventory differs")
        for name, expected in manifest["source_files"].items():
            if Path(name).is_absolute() or ".." in Path(name).parts:
                raise ValueError("unsafe source archive path")
            if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                raise ValueError("archived writer source differs: " + name)
            if source is not None and mp.file_sha256(Path(source) / name) != expected:
                raise ValueError("current writer source differs: " + name)
    return manifest


def _text_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_family(family, allowance, directory, model, *, commit, deadline=float("inf"), clock=time.monotonic):
    """Eight independent writer chains, 16 literal snapshots; zero reader inference."""
    started = clock()
    unit = mp._Unit(Path(directory), model, deadline, clock)
    for name in ("snapshots.jsonl", "reader-inputs.jsonl"):
        unit.files[name] = (unit.dir / name).open("x", encoding="utf-8")
    try:
        for world in family["worlds"]:
            for fmt in mp.FORMATS:
                snapshots = unit.chain(family, world, fmt, allowance)
                for probe, rendered in snapshots.items():
                    identity = {"family_id": family["family_id"], "world": world["world"],
                                "format": fmt, "allowance": allowance, "probe": probe}
                    snapshot_id = "/".join(map(str, (family["family_id"], world["world"], fmt, allowance, probe)))
                    count = model.count_tokens(rendered)
                    if type(count) is not int or not 0 <= count <= allowance:
                        raise ValueError("invalid exported snapshot token count")
                    snapshot = {**identity, "snapshot_id": snapshot_id, "rendered": rendered,
                        "rendered_sha256": _text_hash(rendered), "token_count": count,
                        "source_write_index": mp.PROBES[probe]}
                    mp._write_line(unit.files["snapshots.jsonl"], snapshot)
                    messages = [asdict(m) for m in mp.reader_messages(
                        rendered, family["roles"]["target"], family["options"])]
                    mp._write_line(unit.files["reader-inputs.jsonl"], {
                        **identity, "snapshot_id": snapshot_id, "notebook_sha256": _text_hash(rendered),
                        "messages": messages, "prompt_sha256": mp.digest(messages),
                        "supported_label": None})  # Annotation, not hidden-world supervision.
        unit.complete({"family_id": family["family_id"], "allowance": allowance,
            "physical_requests": unit.request_id + 1, "wall_seconds": clock() - started,
            "usage": unit.logged.by_purpose, "model_is_fake": model.metadata.get("is_fake") is not False},
            commit)
    finally:
        unit.close()
    return audit_family(Path(directory), family, allowance, real=model.metadata.get("is_fake") is False)


def audit_family(directory, family, allowance, *, real):
    """Reuse the raw-output/repair auditor, then require exact writer/export coverage."""
    directory = Path(directory)
    completion = mp.verify_completion(directory)
    mp._require_exact(list(completion["files"]),
        ["events.jsonl", "writes.jsonl", "assessments.jsonl", "snapshots.jsonl",
         "reader-inputs.jsonl", "summary.json"], "writer family completion inventory")
    audit = mp.audit_unit(directory, [family], real=real)
    if audit["reader_calls"] or audit["assessments"]:
        raise mp.AuditError("writer-only collection contains reader inference")
    writes = _rows(directory / "writes.jsonl")
    mp._require_exact([(w["world"], w["format"], w["allowance"], w["write_index"]) for w in writes],
        [(w, f, allowance, i) for w in range(4) for f in mp.FORMATS for i in range(14)],
        "writer-only write coverage")
    events = _rows(directory / "events.jsonl")
    requests = {e["request_id"]: e for e in events if e["event"] == "model_request"}
    used = [rid for w in writes for rid in w["request_ids"]]
    if len(used) != len(set(used)) or set(used) != set(requests):
        raise mp.AuditError("writer requests do not correspond one-to-one with writes")
    for request in requests.values():
        if request.get("role") != "writer" or request["purpose"] not in {"memory", "memory_repair"}:
            raise mp.AuditError("non-writer call in writer collection")
    indexed = {(w["world"], w["format"], w["write_index"]): w for w in writes}
    snapshots = _rows(directory / "snapshots.jsonl")
    expected = [(w, f, p) for w in range(4) for f in mp.FORMATS for p in mp.PROBES]
    mp._require_exact([(s["world"], s["format"], s["probe"]) for s in snapshots],
                     expected, "snapshot coverage")
    inputs = _rows(directory / "reader-inputs.jsonl")
    mp._require_exact([(s["world"], s["format"], s["probe"]) for s in inputs],
                     expected, "reader-input coverage")
    inputs = {(s["world"], s["format"], s["probe"]): s for s in inputs}
    for snapshot in snapshots:
        w, fmt, probe = snapshot["world"], snapshot["format"], snapshot["probe"]
        stored = indexed[w, fmt, mp.PROBES[probe]]
        text = stored["rendered"]
        key = _text_hash(text)
        snapshot_id = "/".join(map(str, (family["family_id"], w, fmt, allowance, probe)))
        recorded = {c["count"] for c in stored["token_counts"] if c["text_sha256"] == key}
        if (snapshot["rendered"] != text or snapshot["rendered_sha256"] != key
                or recorded != {snapshot["token_count"]} or not 0 <= snapshot["token_count"] <= allowance
                or snapshot["family_id"] != family["family_id"] or snapshot["allowance"] != allowance
                or snapshot["snapshot_id"] != snapshot_id
                or snapshot["source_write_index"] != mp.PROBES[probe]):
            raise mp.AuditError("snapshot differs from stored writer state/count")
        reader = inputs[w, fmt, probe]
        messages = [asdict(m) for m in mp.reader_messages(text, family["roles"]["target"], family["options"])]
        if (reader["messages"] != messages or reader["prompt_sha256"] != mp.digest(messages)
                or reader["notebook_sha256"] != key or reader["snapshot_id"] != snapshot["snapshot_id"]
                or reader["family_id"] != family["family_id"] or reader["allowance"] != allowance
                or reader["supported_label"] is not None):
            raise mp.AuditError("reader export differs or fabricates supervision")
    if real and _read(directory / "summary.json")["model_is_fake"]:
        raise mp.AuditError("fixture family claimed as real")
    return {**audit, "snapshots": len(snapshots)}


def select_allowance(counts):
    if len(counts) != 64 or any(type(n) is not int or not 0 <= n <= ALLOWANCE for n in counts):
        raise ValueError("budget rule requires all 64 valid snapshot counts")
    return 128 if max(counts) <= 128 else 256


class _WriterOnly:
    def __init__(self, model, deadline, clock, limit=REQUEST_CEILING):
        self.model, self.deadline, self.clock, self.calls = model, deadline, clock, 0
        self.limit = limit

    @property
    def metadata(self):
        return self.model.metadata

    def count_tokens(self, text):
        return self.model.count_tokens(text)

    def generate(self, messages, *, purpose):
        if purpose not in {"memory", "memory_repair"}:
            raise ValueError("writer collection forbids reader/generic action calls")
        if self.clock() >= self.deadline:
            raise mp.StageTimeout("writer collection deadline before inference")
        if self.calls >= self.limit:
            raise RuntimeError("writer collection request ceiling")
        self.calls += 1
        return self.model.generate(messages, purpose=purpose)

    def score_choices(self, *args, **kwargs):
        raise ValueError("writer collection forbids reader scoring")


def load_models(manifest, families, output):
    """Known cached runtime; tokenizer-only preflight precedes one stock weight load."""
    from . import transformers_model as tm
    os.environ.update(transport.ENV)
    config = tm.TransformersConfig(revision=mp.MODEL_REVISION, dtype="float16", device="cuda",
        context_limit=8192, action_max_new_tokens=128, memory_max_new_tokens=1024,
        generation_seed=0, local_files_only=True)
    cache = Path("/cache/huggingface/hub/models--Qwen--Qwen3-4B-Instruct-2507/snapshots") / mp.MODEL_REVISION
    runtime, cfg = transport.runtime_and_cache(tm, config, cache)
    transport.save(output / "runtime-cache.json", runtime)
    tokenizer = transport.cached_tokenizer(cache)
    counts = {}
    for family in families:
        for world in family["worlds"]:
            for fmt in mp.FORMATS:
                messages = mp.writer_messages(fmt, mp.WRITERS[fmt]().empty(), mp.INITIAL,
                                              world["observations"][0], ALLOWANCE)
                prompt = tokenizer.apply_chat_template([asdict(m) for m in messages],
                                                       tokenize=False, add_generation_prompt=True)
                count = len(tokenizer.encode(prompt, add_special_tokens=False))
                if count + 1024 > 8192:
                    raise ValueError("initial writer context overflow; no truncation")
                counts[f"{family['family_id']}/{world['world']}/{fmt}"] = count
    transport.save(output / "tokenizer-preflight.json", {
        "evidence": "actual_cached_tokenizer", "initial_prompts": counts,
        "test_family_inference": False})
    model = tm.TransformersModel(config)
    transport.save(output / "model.json", model.metadata)
    return model, lambda text: len(tokenizer.encode(text, add_special_tokens=False))


def _verified_reuse(reuse, manifest, families):
    """Completed units only; explicit hashes pin the interrupted source attempt."""
    known = {f["family_id"]: f for f in families}
    verified = {}
    for item in reuse:
        fid, directory = item["family_id"], Path(item["directory"])
        if fid not in known or fid in verified:
            raise mp.AuditError("unknown/duplicate reused calibration family")
        origin = _read(directory.parent / "entry.json")["manifest"]
        if (origin["manifest_sha256"] != item["source_manifest_sha256"]
                or mp.digest({k: v for k, v in origin.items() if k != "manifest_sha256"})
                   != item["source_manifest_sha256"]
                or mp.file_sha256(directory / "completion.json") != item["completion_sha256"]):
            raise mp.AuditError("reused source identity/completion differs")
        for key in ("protocol", "model", "writer_version", "reader_version", "calibration_allowance"):
            if origin[key] != manifest[key]:
                raise mp.AuditError("reused writer/split settings differ")
        if (origin["splits"]["calibration"] != manifest["splits"]["calibration"]
                or mp.file_sha256(directory.parent / "calibration-families.json")
                   != manifest["splits"]["calibration"]["sha256"]):
            raise mp.AuditError("reused calibration split differs")
        for name in (*mp.SOURCE_FILES, "game_memory/memory_probe_modal.py"):
            if origin["source_files"][name] != manifest["source_files"][name]:
                raise mp.AuditError("reused writer/auditor dependency differs: " + name)
        source_status = _read(directory.parent / "status.json")
        model = _read(directory.parent / "model.json")
        if (model.get("is_fake") is not False) != source_status["model_is_fake"]:
            raise mp.AuditError("reused model identity differs")
        audit = audit_family(directory, known[fid], ALLOWANCE, real=not source_status["model_is_fake"])
        verified[fid] = {**item, "directory": str(directory), "audit": audit, "source_model": model,
            "source_status_sha256": mp.file_sha256(directory.parent / "status.json")}
    return verified


def calibrate(package, output, *, loader, commit, clock=time.monotonic, reuse=()):
    manifest = verify_package(package, source=Path(__file__).resolve().parents[1])
    package, output = Path(package), Path(output)
    families = _read(package / manifest["splits"]["calibration"]["path"])
    output.mkdir(parents=True, exist_ok=False)
    started = clock()
    deadline = started + SOFT_SECONDS
    shutil.copyfile(package / manifest["splits"]["calibration"]["path"], output / "calibration-families.json")
    transport.save(output / "entry.json", {"manifest": manifest, "started_monotonic": started})
    commit()
    status = {"complete": False, "completed_families": [], "manifest_sha256": manifest["manifest_sha256"],
              "reused_requests": 0}
    guarded, original = None, None
    try:
        verified = _verified_reuse(reuse, manifest, families)
        transport.save(output / "reuse.json", list(verified.values()))
        model, recount = loader(manifest, families, output)
        if not (output / "model.json").exists():
            transport.save(output / "model.json", model.metadata)
        status["model_is_fake"] = model.metadata.get("is_fake") is not False
        guarded = _WriterOnly(model, deadline, clock, (4 - len(verified)) * 224)
        for family in families:
            fid = family["family_id"]
            if fid in verified:
                source = verified[fid]
                keys = ("is_fake", "model_id", "revision", "dtype", "device", "context_limit",
                        "generation_seed", "memory_max_new_tokens", "do_sample", "use_model_defaults")
                if any(source["source_model"].get(k) != model.metadata.get(k) for k in keys):
                    raise mp.AuditError("reused/new model configuration differs")
                shutil.copytree(source["directory"], output / fid)
                audit = audit_family(output / fid, family, ALLOWANCE, real=not status["model_is_fake"])
                status["reused_requests"] += audit["requests"]
                commit()
            else:
                write_family(family, ALLOWANCE, output / fid, guarded,
                             commit=commit, deadline=deadline, clock=clock)
            status["completed_families"].append(family["family_id"])
        measurements = []
        for family in families:
            for snapshot in _rows(output / family["family_id"] / "snapshots.jsonl"):
                actual = recount(snapshot["rendered"])
                if type(actual) is not int or actual != snapshot["token_count"]:
                    raise mp.AuditError("independent cached-tokenizer snapshot recount differs")
                measurements.append({"snapshot_id": snapshot["snapshot_id"],
                    "rendered_sha256": snapshot["rendered_sha256"], "token_count": actual})
        low = select_allowance([m["token_count"] for m in measurements])
        transport.save(output / "snapshot-recount.json", {
            "evidence": "synthetic_fixture" if status["model_is_fake"] else "actual_cached_tokenizer",
            "measurements": measurements})
        transport.save(output / "calibration-decision.json", {"complete": True,
            "selected_allowance": low, "snapshot_count": 64,
            "max_snapshot_tokens": max(m["token_count"] for m in measurements),
            "rule": manifest["budget_rule"], "model_is_fake": status["model_is_fake"]})
        status.update(complete=True, outcome="calibration_complete")
    except BaseException as error:
        original = error
        status.update(outcome="error", error_type=type(error).__name__, error=str(error),
                      traceback=traceback.format_exc())
        raise
    finally:
        new_requests = guarded.calls if guarded else 0
        status.update(new_attempted_requests=new_requests,
                      attempted_requests=new_requests + status["reused_requests"],
                      wall_seconds=clock() - started)
        try:
            transport.save(output / "status.json", status)
            commit()
        except BaseException as cleanup:
            if original is None:
                raise
            original.add_note(f"Persisting collection status also failed: {cleanup!r}")
    transport.save(output / "completion.json", {"files": {
        str(p.relative_to(output)): mp.file_sha256(p) for p in sorted(output.rglob("*")) if p.is_file()}})
    commit()
    return report(output)


def report(output):
    output = Path(output)
    status = _read(output / "status.json")
    entry = _read(output / "entry.json")
    manifest = entry["manifest"]
    if mp.file_sha256(output / "calibration-families.json") != manifest["splits"]["calibration"]["sha256"]:
        raise mp.AuditError("calibration families differ")
    families = _read(output / "calibration-families.json")
    audits, snapshots, events = [], [], []
    for family in families:
        directory = output / family["family_id"]
        if (directory / "events.jsonl").exists():
            events += _rows(directory / "events.jsonl")
        if (directory / "completion.json").exists():
            audits.append(audit_family(directory, family, ALLOWANCE,
                                      real=status.get("model_is_fake") is False))
            snapshots += _rows(directory / "snapshots.jsonl")
    selected = None
    if status["complete"]:
        completion = _read(output / "completion.json")["files"]
        mp._require_exact(list(completion),
            [str(p.relative_to(output)) for p in output.rglob("*")
             if p.is_file() and p != output / "completion.json"], "collection completion inventory")
        for name, expected in completion.items():
            if mp.file_sha256(output / name) != expected:
                raise mp.AuditError("collection completion hash differs: " + name)
        if len(audits) != 4 or len(snapshots) != 64:
            raise mp.AuditError("complete calibration has incomplete family/snapshot coverage")
        measured = _read(output / "snapshot-recount.json")
        mp._require_exact([m["snapshot_id"] for m in measured["measurements"]],
                         [s["snapshot_id"] for s in snapshots], "snapshot recount coverage")
        by_id = {s["snapshot_id"]: s for s in snapshots}
        for m in measured["measurements"]:
            s = by_id[m["snapshot_id"]]
            if m["rendered_sha256"] != s["rendered_sha256"] or m["token_count"] != s["token_count"]:
                raise mp.AuditError("snapshot recount does not reconcile")
        selected = select_allowance([m["token_count"] for m in measured["measurements"]])
        decision = _read(output / "calibration-decision.json")
        if decision != {"complete": True, "selected_allowance": selected, "snapshot_count": 64,
                "max_snapshot_tokens": max(s["token_count"] for s in snapshots),
                "rule": manifest["budget_rule"], "model_is_fake": status["model_is_fake"]}:
            raise mp.AuditError("budget decision differs from frozen rule")
    responses = [e for e in events if e["event"] == "model_response"]
    requests = [e for e in events if e["event"] == "model_request"]
    writes = [w for family in families for w in (
        _rows(output / family["family_id"] / "writes.jsonl")
        if (output / family["family_id"] / "writes.jsonl").exists() else [])]
    if status["complete"] and (status["completed_families"] != [f["family_id"] for f in families]
            or status["attempted_requests"] != len(requests)
            or len(requests) != len(responses) or len(requests) > REQUEST_CEILING):
        raise mp.AuditError("completed collection request/family accounting differs")
    cells = {}
    for fmt in mp.FORMATS:
        chosen = [s for s in snapshots if s["format"] == fmt]
        cells[fmt] = {"snapshots": len(chosen),
            "min_tokens": min((s["token_count"] for s in chosen), default=None),
            "max_tokens": max((s["token_count"] for s in chosen), default=None),
            "empty_snapshots": sum(s["rendered"] in {"", "{}"} for s in chosen),
            "repairs": sum(len(w["request_ids"]) == 2 for w in writes if w["format"] == fmt),
            "fallbacks": sum("memory_fallback:previous_valid_memory" in w["update_events"]
                             for w in writes if w["format"] == fmt)}
    reuse = _read(output / "reuse.json") if (output / "reuse.json").exists() else []
    if status["complete"] and status.get("reused_requests", 0) != sum(r["audit"]["requests"] for r in reuse):
        raise mp.AuditError("reused request accounting differs")
    if status["complete"]:
        for item in reuse:
            if mp.file_sha256(output / item["family_id"] / "completion.json") != item["completion_sha256"]:
                raise mp.AuditError("reused unit bytes differ from pinned source")
        if (status.get("new_attempted_requests", status["attempted_requests"])
                + status.get("reused_requests", 0) != status["attempted_requests"]):
            raise mp.AuditError("new/reused request accounting differs")
    return {"status": status, "complete": status["complete"], "selected_allowance": selected,
        "reused_units": reuse,
        "usage_scope": "Distinct physical requests represented in this corpus, including explicitly reused units; new GPU attempts are recorded separately.",
        "audits": audits, "cells": cells, "snapshots": snapshots,
        "known_usage": {"request_records": len(requests), "responses": len(responses),
            "unknown_usage_requests": len(requests) - len(responses),
            "primary_calls": sum(r["purpose"] == "memory" for r in responses),
            "repair_calls": sum(r["purpose"] == "memory_repair" for r in responses),
            "input_tokens": sum(r["input_tokens"] for r in responses),
            "output_tokens": sum(r["output_tokens"] for r in responses),
            "generation_seconds": sum(r["elapsed_seconds"] for r in responses)},
        "limits": "Writer-only development collection. No reader accuracy, factual retention, or training result is established."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare", help="offline split/source freeze, no model or tokenizer")
    prep.add_argument("--output-dir", type=Path, required=True)
    run = sub.add_parser("calibrate", help="standing-authorized GPU C00-C03 writer-only pilot")
    run.add_argument("--package", type=Path, required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    show = sub.add_parser("report", help="read-only; keep redirected stdout outside the run")
    show.add_argument("directory", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.output_dir)
    elif args.command == "report":
        result = report(args.directory)
    else:
        result = calibrate(args.package, args.output_dir, loader=load_models, commit=lambda: None)
    print(json.dumps(result, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
