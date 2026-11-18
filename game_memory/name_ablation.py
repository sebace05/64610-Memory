"""Small, frozen name/distractor ablation; no generator changes or optional imports."""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import time
import traceback
import zipfile

from . import memory_probe as mp
from . import reader_diagnostic as rd
from .runner import _LoggedModel

VERSION = "name-ablation-v1"
ALIASES = ("balok", "zomip")
SOFT_SECONDS = 540
SOURCE_FILES = tuple(dict.fromkeys((*rd.SOURCE_FILES, "game_memory/name_ablation.py",
                                  "tests/test_name_ablation.py", "docs/name-ablation-v1.md")))


def roles(family, state):
    """Focal roles are fixed; controls use a deterministic same-value distractor pair."""
    if family["family_id"] == "Q00":
        return dict(suspect="tuven", control="visuv", neighbor="pisak", far="gitix")
    target, revoked = family["roles"]["target"], family["roles"]["revoked"]
    order = sorted(state)
    i = order.index(target)
    candidates = [n for n in order[i + 1:] + order[:i] if n != revoked]
    suspect = next(n for n in candidates if any(state[n] == state[m] for m in candidates if m != n))
    control = next(n for n in candidates if n != suspect and state[n] == state[suspect])
    neighbor = next(n for n in order[:i][::-1] + order[i + 1:][::-1]
                    if n not in {suspect, control, revoked})
    far = next(n for n in candidates if n not in {suspect, control, neighbor})
    return dict(suspect=suspect, control=control, neighbor=neighbor, far=far)


def cases(historical_unit=None):
    historical, provenance = rd.cases(historical_unit)
    originals = {(c["family_id"], c["world"], c["format"]): c
                 for c in historical if c["variant"] == "original"}
    families = {f["family_id"]: f for f in mp.generate_splits()["qualification"]}
    result = []
    for fid, wi in rd.SELECTION:
        family = families[fid]
        reduced = mp.public_state(family["worlds"][wi]["observations"])
        base, target = reduced["state"], family["roles"]["target"]
        chosen = roles(family, base)
        if any(n in base for n in ALIASES) or base[chosen["suspect"]] != base[chosen["control"]]:
            raise ValueError("alias collision or unmatched distractor values")
        for fmt in mp.FORMATS:
            original = originals[fid, wi, fmt]
            variants = [("original", {}, {}, original["entity_order"]),
                        ("matched_lexical", {}, {}, sorted(base))]
            for role, entity in (("suspect", chosen["suspect"]), ("query", target),
                                 ("control", chosen["control"])):
                for alias in ALIASES:
                    variants.append((f"rename_{role}_{alias}", {entity: alias}, {}, sorted(base)))
            for role in ("suspect", "control"):
                entity = chosen[role]
                for value in mp.DESTINATIONS:
                    if value != base[entity]:
                        variants.append((f"value_{role}_{value}", {}, {entity: value}, sorted(base)))
            for role in ("neighbor", "far"):
                order = sorted(base)
                i, j = order.index(chosen["suspect"]), order.index(chosen[role])
                order[i], order[j] = order[j], order[i]
                variants.append((f"swap_suspect_{role}", {}, {}, order))
            for variant, rename, changed, order in variants:
                state = {rename.get(n, n): changed.get(n, base[n]) for n in order}
                query = rename.get(target, target)
                memory = (mp.prose_note(dict(order=list(state), state=state)) if fmt == "prose"
                          else json.dumps(state, ensure_ascii=False, separators=(",", ":")))
                messages = [asdict(m) for m in mp.reader_messages(memory, query, family["options"])]
                if variant == "original" and messages != original["messages"]:
                    raise ValueError("historical original prompt reconstruction differs")
                result.append(dict(case_id=f"{fid}/{wi}/{fmt}/{variant}", family_id=fid, world=wi,
                    format=fmt, variant=variant, role=original["role"], query=query, gold=original["gold"],
                    options=original["options"], entity_order=list(state), state=state, memory=memory,
                    distractor_roles=chosen, renames=rename, value_changes=changed,
                    messages=messages, prompt_sha256=mp.digest(messages)))
    return result, provenance


def methods(case):
    chosen = ["restricted"]
    if case["variant"] in {"original", "matched_lexical"}:
        chosen.append("reference")
    if case["family_id"] == "Q00" and case["variant"] == "matched_lexical":
        chosen.append("repeat")
    return chosen


def schedule(entries):
    # Baseline repeats occur after every intervention; other identities can reuse exact inputs.
    return ([(c, m) for c in entries for m in methods(c) if m != "repeat"]
            + [(c, "repeat") for c in entries if "repeat" in methods(c)])


def prepare(output, *, historical_unit=None):
    entries, provenance = cases(historical_unit)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    rd.transport.save(output / "cases.json", entries)
    source = Path(__file__).resolve().parents[1]
    with zipfile.ZipFile(output / "source.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in SOURCE_FILES:
            archive.write(source / name, name)
    manifest = dict(version=VERSION, provenance=provenance, selection=list(rd.SELECTION), aliases=ALIASES,
        logical_cases=len(entries), unique_prompts=len({c["prompt_sha256"] for c in entries}),
        request_ceiling=len({(c["prompt_sha256"], m) for c, m in schedule(entries)}),
        soft_seconds=SOFT_SECONDS, execution_seconds=600, model=dict(id=mp.MODEL_ID,
        revision=mp.MODEL_REVISION, dtype="float16", context_limit=8192, seed=0),
        files={n: mp.file_sha256(output / n) for n in ("cases.json", "source.zip")},
        source_files={n: mp.file_sha256(source / n) for n in SOURCE_FILES})
    manifest["manifest_sha256"] = mp.digest(manifest)
    rd.transport.save(output / "manifest.json", manifest)
    return manifest


def verify_package(package, source=None):
    package = Path(package)
    manifest = rd._read(package / "manifest.json")
    if (manifest["version"] != VERSION or manifest["manifest_sha256"] != mp.digest(
            {k: v for k, v in manifest.items() if k != "manifest_sha256"})):
        raise ValueError("ablation manifest differs")
    if (manifest["aliases"] != list(ALIASES) or manifest["selection"] != [list(x) for x in rd.SELECTION]
            or manifest["soft_seconds"] != SOFT_SECONDS or manifest["execution_seconds"] != 600
            or manifest["model"] != dict(id=mp.MODEL_ID, revision=mp.MODEL_REVISION,
                                        dtype="float16", context_limit=8192, seed=0)):
        raise ValueError("ablation settings differ")
    for name, expected in manifest["files"].items():
        if mp.file_sha256(package / name) != expected:
            raise ValueError("ablation package bytes differ")
    with zipfile.ZipFile(package / "source.zip") as archive:
        if sorted(archive.namelist()) != sorted(SOURCE_FILES) or set(manifest["source_files"]) != set(SOURCE_FILES):
            raise ValueError("ablation source inventory differs")
        for name, expected in manifest["source_files"].items():
            if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                raise ValueError("archived ablation source differs")
            if source is not None and mp.file_sha256(Path(source) / name) != expected:
                raise ValueError("current ablation source differs: " + name)
    entries = rd._read(package / "cases.json")
    if entries != cases()[0]:
        raise ValueError("ablation cases differ from fixed construction")
    if (manifest["logical_cases"] != len(entries)
            or manifest["unique_prompts"] != len({c["prompt_sha256"] for c in entries})
            or manifest["request_ceiling"] != len({(c["prompt_sha256"], m) for c, m in schedule(entries)})):
        raise ValueError("ablation coverage/ceiling differs")
    return manifest, entries


def token_evidence(entries, tokenizer, *, fake):
    names = sorted({n for c in entries for n in c["entity_order"]})
    tokens = {}
    for name in names:
        contexts = dict(bare=name, space=" " + name, json_key='"' + name + '":', capitalized=name.capitalize())
        tokens[name] = {}
        for label, text in contexts.items():
            ids = tokenizer.encode(text, add_special_tokens=False)
            tokens[name][label] = dict(text=text, ids=ids, pieces=tokenizer.convert_ids_to_tokens(ids))
    # Exact prompt offsets for the focal baseline, including note and query occurrences.
    occurrences = []
    import re
    for case in entries:
        if (case["family_id"], case["world"], case["variant"]) != ("Q00", 0, "matched_lexical"):
            continue
        prompt, prefix, _ = rd.reference_tokens(tokenizer, rd._messages(case))
        encoded = tokenizer(prompt, add_special_tokens=False, return_offsets_mapping=True)
        if encoded["input_ids"] != prefix:
            raise ValueError("offset tokenization differs from scored prompt")
        for name in case["entity_order"]:
            for match in re.finditer(r"(?<![a-z])" + name + r"(?![a-z])", prompt, re.IGNORECASE):
                selected = [i for i, (a, b) in enumerate(encoded["offset_mapping"])
                            if a < match.end() and b > match.start()]
                ids = [prefix[i] for i in selected]
                occurrences.append(dict(case_id=case["case_id"], name=name,
                    span=[match.start(), match.end()], ids=ids, pieces=tokenizer.convert_ids_to_tokens(ids)))
    return dict(evidence="synthetic_fixture" if fake else "actual_cached_tokenizer", names=tokens,
                focal_baseline_occurrences=occurrences)


def load_models(manifest, entries, output):
    model, reference = rd.load_models(manifest, entries, output)
    rd.transport.save(output / "name-tokens.json", token_evidence(entries, model._tokenizer, fake=False))
    return model, reference


def run(package, output, *, loader=load_models, clock=time.monotonic):
    manifest, entries = verify_package(package, source=Path(__file__).resolve().parents[1])
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    started = clock()
    rd.transport.save(output / "entry.json", dict(manifest=manifest))
    rd.transport.save(output / "cases.json", entries)
    status = dict(complete=False, manifest_sha256=manifest["manifest_sha256"])
    requests, sequence, context, cache = 0, 0, {}, {}
    original = None
    with (output / "events.jsonl").open("x") as events, (output / "assessments.jsonl").open("x") as rows:
        def emit(event, **data):
            nonlocal sequence
            mp._write_line(events, dict(event=event, sequence=sequence, **context, **data))
            sequence += 1
        try:
            model, reference = loader(manifest, entries, output)
            status.update(model_is_fake=model.metadata.get("is_fake") is not False,
                          reference_is_fake=reference.metadata.get("is_fake") is not False)
            primary, other = _LoggedModel(model, emit, lambda: requests - 1), _LoggedModel(reference, emit, lambda: requests - 1)
            for case, method in schedule(entries):
                key = case["prompt_sha256"], method
                reused = key in cache
                if not reused:
                    if clock() - started >= SOFT_SECONDS:
                        raise TimeoutError("ablation deadline before inference")
                    if requests >= manifest["request_ceiling"]:
                        raise RuntimeError("ablation request ceiling")
                    context.update(method=method, case_id=case["case_id"], request_id=requests)
                    requests += 1
                    result = (other if method == "reference" else primary).score_choices(rd._messages(case), labels=mp.LABELS)
                    cache[key] = result, requests - 1
                result, source_id = cache[key]
                if result.text != rd.reference_argmax(result.metadata["candidate_logits"]):
                    raise ValueError("selected label disagrees with raw logits")
                if method == "reference" and not rd.compare_scores(cache[case["prompt_sha256"], "restricted"][0], result):
                    raise ValueError("reference differs; inspect raw evidence")
                destination = case["options"][mp.LABELS.index(result.text)]
                mp._write_line(rows, dict(case_id=case["case_id"], method=method, source_request_id=source_id,
                    reused=reused, selected_letter=result.text, selected_destination=destination,
                    correct=destination == case["gold"]))
            status.update(complete=True, outcome="ablation_complete")
        except BaseException as error:
            original = error
            status.update(outcome="error", error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc())
            raise
        finally:
            events.flush(); os.fsync(events.fileno()); rows.flush(); os.fsync(rows.fileno())
            status.update(attempted_requests=requests, wall_seconds=clock() - started)
            try:
                rd.transport.save(output / "status.json", status)
            except BaseException as cleanup:
                if original is None:
                    raise
                original.add_note(f"Saving ablation status also failed: {cleanup!r}")
    rd.transport.save(output / "completion.json", {p.name: mp.file_sha256(p)
                   for p in output.iterdir() if p.is_file()})
    return report(output)


def report(output):
    output = Path(output)
    status = rd._read(output / "status.json")
    if status["complete"]:
        for name, expected in rd._read(output / "completion.json").items():
            if mp.file_sha256(output / name) != expected:
                raise ValueError("ablation completion hash differs")
    entries = rd._read(output / "cases.json")
    if entries != cases()[0]:
        raise ValueError("reported cases differ from fixed ablation")
    expected = {c["case_id"]: c for c in entries}
    rows, events = rd._rows(output / "assessments.jsonl"), rd._rows(output / "events.jsonl")
    requests = {e["request_id"]: e for e in events if e["event"] == "model_request"}
    responses = {e["request_id"]: e for e in events if e["event"] == "model_response"}
    if (len(requests) != sum(e["event"] == "model_request" for e in events)
            or len(responses) != sum(e["event"] == "model_response" for e in events)):
        raise ValueError("duplicate ablation request/response ID")
    keys = [(r["case_id"], r["method"]) for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate ablation assessment")
    if status["complete"] and (set(keys) != {(c["case_id"], m) for c, m in schedule(entries)}
            or set(requests) != set(responses) or sorted(requests) != list(range(len(requests)))
            or status["attempted_requests"] != len(requests)
            or len(requests) != len({(c["prompt_sha256"], m) for c, m in schedule(entries)})):
        raise ValueError("incomplete ablation coverage/accounting")
    sources, bindings = {}, {}
    for c, method in schedule(entries):
        key = c["prompt_sha256"], method
        reused = key in sources
        if not reused:
            sources[key] = len(sources)
        bindings[c["case_id"], method] = sources[key], reused
    cells, results, repeats = {}, {}, []
    for row in rows:
        c, rid = expected[row["case_id"]], row["source_request_id"]
        if (rid, row["reused"]) != bindings[row["case_id"], row["method"]]:
            raise ValueError("ablation physical-call reuse differs from fixed schedule")
        request, response = requests[rid], responses[rid]
        label = rd.reference_argmax(response["metadata"]["candidate_logits"])
        destination = c["options"][mp.LABELS.index(label)]
        if (request["messages"] != c["messages"] or request["method"] != row["method"]
                or request["purpose"] != "action" or response["text"] != label
                or row["selected_letter"] != label or row["selected_destination"] != destination
                or row["correct"] != (destination == c["gold"])):
            raise ValueError("ablation row differs from raw scoring evidence")
        evidence = "independent_raw_forward" if row["method"] == "reference" else "actual_model_forward"
        if status.get("model_is_fake") is False and response["metadata"].get("scoring_evidence") != evidence:
            raise ValueError("real ablation lacks actual forward evidence")
        results[c["case_id"], row["method"]] = response
        if row["method"] == "restricted":
            key = "/".join((c["role"], c["format"], c["variant"]))
            cell = cells.setdefault(key, dict(correct=0, total=0, destinations={}))
            cell["total"] += 1; cell["correct"] += row["correct"]
            cell["destinations"][destination] = cell["destinations"].get(destination, 0) + 1
    if status["complete"]:
        for c, method in schedule(entries):
            if method != "restricted":
                pair = [_generation(results[c["case_id"], m]) for m in ("restricted", method)]
                if method == "reference" and not rd.compare_scores(*pair):
                    raise ValueError("reported reference differs")
                if method == "repeat":
                    repeats.append(dict(case_id=c["case_id"], label_agrees=pair[0].text == pair[1].text,
                        logits_agree=rd.compare_scores(*pair), max_abs_logit_difference=max(abs(a-b) for a,b in zip(
                            pair[0].metadata["candidate_logits"], pair[1].metadata["candidate_logits"]))))
    return dict(status=status, cells=cells, assessments=rows, baseline_repeats=repeats,
        physical_responses=len(responses), known_input_tokens=sum(r["input_tokens"] for r in responses.values()),
        known_output_tokens=sum(r["output_tokens"] for r in responses.values()),
        known_model_seconds=sum(r["elapsed_seconds"] for r in responses.values()),
        unknown_usage_requests=len(requests)-len(responses),
        limits="Exploratory selected development cases; no new task, writer, test set, or fine-tuning result.")


def _generation(response):
    from .components import Generation
    return Generation(**{k: response[k] for k in ("text", "input_tokens", "output_tokens", "elapsed_seconds", "metadata")})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--output-dir", type=Path, required=True)
    prep.add_argument("--historical-unit", type=Path)
    execute = sub.add_parser("run", help="standing-authorized cached Qwen GPU diagnostic")
    execute.add_argument("--package", type=Path, required=True)
    execute.add_argument("--output-dir", type=Path, required=True)
    show = sub.add_parser("report")
    show.add_argument("directory", type=Path)
    args = parser.parse_args()
    result = (prepare(args.output_dir, historical_unit=args.historical_unit) if args.command == "prepare"
              else report(args.directory) if args.command == "report" else run(args.package, args.output_dir))
    print(json.dumps(result, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
