"""reader-diagnostic-v1: offline preparation/reporting; opt-in cached GPU execution.

The v1 experiment is imported unchanged. No optional inference packages are
imported and no model is constructed until the authorized run boundary.
"""

import argparse
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
import traceback
import zipfile

from . import memory_probe as mp
from . import memory_probe_modal as transport
from .components import Generation, Message
from .runner import _LoggedModel

VERSION = "reader-diagnostic-v1"
# Frozen before diagnostic inference: four focal siblings, two controls per stratum.
SELECTION = (("Q00", 0), ("Q00", 1), ("Q00", 2), ("Q00", 3),
             ("Q01", 0), ("Q01", 1), ("Q02", 2), ("Q02", 3))
METHODS = ("restricted", "reference", "generated")
GENERATION_CAP = 32
LOGIT_ATOL = 0.0625
SOFT_SECONDS = 1740
HISTORICAL_HASHES = {
    "events.jsonl": "a73aad299ac7aefcecba51659e03024a81c1b89692328ca482631102ae1b1ec4",
    "assessments.jsonl": "a411a80b2918195d10f1b1b8b67609a5c6f8201a133c46ed139d7a14966a613c",
}
SOURCE_FILES = (*mp.SOURCE_FILES, "game_memory/memory_probe_modal.py",
                "game_memory/reader_diagnostic.py", "tests/test_reader_diagnostic.py",
                "tests/test_transformers_model.py",
                "docs/reader-diagnostic-v1.md", "docs/matched-reader-training-v1.md")


def _read(path):
    return json.loads(Path(path).read_text())


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def _messages(case):
    return tuple(Message(**m) for m in case["messages"])


def cases(historical_unit=None):
    """Construct fixed variants, optionally verify originals against recorded bytes.

    A clean checkout can reconstruct inputs, but cannot establish an observed
    replay or previously correct responses without the original hashed evidence.
    """
    families = mp.generate_splits()["qualification"]
    observed = {}
    provenance = {"kind": "reconstructed_v1_inputs_not_verified_historical_replay",
                  "historical_hashes": None}
    if historical_unit is not None:
        unit = Path(historical_unit)
        for name, expected in HISTORICAL_HASHES.items():
            if mp.file_sha256(unit / name) != expected:
                raise ValueError(f"historical evidence hash differs: {name}")
        mp.qualification_gate(unit, families, real=True)  # Audits, never infers.
        events = _rows(unit / "events.jsonl")
        requests = {e["request_id"]: e for e in events if e["event"] == "model_request"}
        for row in _rows(unit / "assessments.jsonl"):
            observed[row["family_id"], row["world"], row["condition"]] = (
                row, requests[row["source_request_id"]]["messages"])
        provenance = {"kind": "hash_verified_historical_replay",
                      "historical_hashes": HISTORICAL_HASHES}
    result = []
    for fid, world_index in SELECTION:
        family = next(f for f in families if f["family_id"] == fid)
        world = family["worlds"][world_index]
        reduced = mp.public_state(world["observations"])
        lexical = sorted(reduced["state"])
        for fmt in mp.FORMATS:
            original = next(e for e in mp.qualification_reads(family)
                            if e["world"] == world_index and e["condition"] == f"sufficient_{fmt}")
            original_messages = [asdict(m) for m in mp.reader_messages(
                original["memory"], original["query"], family["options"])]
            recorded = observed.get((fid, world_index, f"sufficient_{fmt}"))
            if recorded is not None:
                row, historical_messages = recorded
                if historical_messages != original_messages:
                    raise ValueError("reconstructed prompt differs from historical request")
                if fid != "Q00" and not row["correct"]:
                    raise ValueError("prespecified control was not previously correct")
            variants = [("original", reduced["order"] if fmt == "prose" else lexical,
                         family["options"], original["memory"]),
                        ("matched_lexical", lexical, family["options"], None),
                        ("matched_reverse", lexical[::-1], family["options"], None)]
            # Rotations are relative to matched_lexical: only option order changes.
            for shift in range(1, len(mp.LABELS)):
                opts = family["options"][shift:] + family["options"][:shift]
                variants.append((f"options_rotate_{shift}", lexical, opts, None))
            for variant, order, options, memory in variants:
                if memory is None:
                    ordered = {n: reduced["state"][n] for n in order}
                    # Deliberately preserve order; v1's canonical JSON sorter is unchanged.
                    memory = (json.dumps(ordered, separators=(",", ":"), ensure_ascii=False)
                              if fmt == "json" else mp.prose_note({"order": order, "state": ordered}))
                messages = [asdict(m) for m in mp.reader_messages(memory, original["query"], options)]
                result.append({"case_id": f"{fid}/{world_index}/{fmt}/{variant}",
                    "family_id": fid, "world": world_index, "format": fmt, "variant": variant,
                    "role": "focal" if fid == "Q00" else "previously_correct_control",
                    "query": original["query"], "gold": original["gold"],
                    "entity_order": list(order), "options": list(options), "memory": memory,
                    "messages": messages, "prompt_sha256": mp.digest(messages),
                    "historical_correct": recorded[0]["correct"] if recorded else None})
    return result, provenance


def prepare(output, *, historical_unit=None, source=None):
    source = Path(source or Path(__file__).resolve().parents[1])
    entries, provenance = cases(historical_unit)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    transport.save(output / "cases.json", entries)
    with zipfile.ZipFile(output / "source.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in SOURCE_FILES:
            archive.write(source / name, name)
    unique = len({c["prompt_sha256"] for c in entries})
    manifest = {"version": VERSION, "provenance": provenance,
        "selection": [list(x) for x in SELECTION], "methods": list(METHODS),
        "logical_prompts": len(entries), "unique_prompts": unique,
        "request_ceiling": 3 * unique, "generation_cap": GENERATION_CAP,
        "max_generated_tokens": unique * GENERATION_CAP,
        "model": {"id": mp.MODEL_ID, "revision": mp.MODEL_REVISION,
                  "dtype": "float16", "device": "cuda", "context_limit": 8192, "seed": 0},
        "logit_absolute_tolerance": LOGIT_ATOL, "soft_seconds": SOFT_SECONDS,
        "extraction": "trim whitespace; exact uppercase A-E with optional final period; else unparseable",
        "files": {n: mp.file_sha256(output / n) for n in ("cases.json", "source.zip")},
        "source_files": {n: mp.file_sha256(source / n) for n in SOURCE_FILES}}
    manifest["manifest_sha256"] = mp.digest(manifest)
    transport.save(output / "manifest.json", manifest)
    (output / "authorization-template.txt").open("x").write(
        "TEMPLATE — NOT EXECUTION AUTHORIZATION\n" + authorization(manifest) + "\n")
    return manifest


def verify_package(package, *, source=None):
    package = Path(package)
    manifest = _read(package / "manifest.json")
    if manifest["manifest_sha256"] != mp.digest({k: v for k, v in manifest.items()
                                                if k != "manifest_sha256"}):
        raise ValueError("diagnostic manifest hash differs")
    if manifest["version"] != VERSION or manifest["methods"] != list(METHODS):
        raise ValueError("unexpected diagnostic settings")
    for name, expected in manifest["files"].items():
        if mp.file_sha256(package / name) != expected:
            raise ValueError(f"diagnostic package hash differs: {name}")
    with zipfile.ZipFile(package / "source.zip") as archive:
        if sorted(archive.namelist()) != sorted(manifest["source_files"]):
            raise ValueError("diagnostic source inventory differs")
        for name, expected in manifest["source_files"].items():
            if Path(name).is_absolute() or ".." in Path(name).parts:
                raise ValueError("unsafe source path")
            if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                raise ValueError(f"archived source differs: {name}")
            if source is not None and mp.file_sha256(Path(source) / name) != expected:
                raise ValueError(f"current source differs: {name}")
    entries = _read(package / "cases.json")
    reconstructed, _ = cases()
    if [{k: v for k, v in c.items() if k != "historical_correct"} for c in entries] != [
            {k: v for k, v in c.items() if k != "historical_correct"} for c in reconstructed]:
        raise ValueError("diagnostic cases differ from the prespecified construction")
    unique = {mp.digest(c["messages"]) for c in entries}
    if (len(entries) != manifest["logical_prompts"] or len(unique) != manifest["unique_prompts"]
            or manifest["request_ceiling"] != 3 * len(unique)
            or manifest["generation_cap"] != GENERATION_CAP):
        raise ValueError("diagnostic coverage/ceiling differs")
    if any(c["prompt_sha256"] != mp.digest(c["messages"]) for c in entries):
        raise ValueError("case prompt hash differs")
    return manifest, entries


def authorization(manifest):
    return (f"I authorize {VERSION} package {manifest['manifest_sha256']}: one cached Qwen load, "
            f"at most {manifest['request_ceiling']} requests including "
            f"{manifest['unique_prompts']} greedy generations capped at {GENERATION_CAP} tokens; "
            "one A10/A10G, 1800-second execution cap, zero retries. No downloads, training, "
            "writer calls, new test families, or resubmission.")


def reference_tokens(tokenizer, messages, labels=mp.LABELS):
    """Independent tokenization/validation; does not call production scoring helpers."""
    prompt = tokenizer.apply_chat_template([asdict(m) for m in messages],
                                           tokenize=False, add_generation_prompt=True)
    prefix = tokenizer.encode(prompt, add_special_tokens=False)
    ids = []
    for label in labels:
        one = tokenizer.encode(label, add_special_tokens=False)
        extended = tokenizer.encode(prompt + label, add_special_tokens=False)
        if (len(one) != 1 or one[0] in tokenizer.all_special_ids
                or extended != prefix + one or one[0] in ids):
            raise ValueError("reference label encoding invalid")
        ids.append(one[0])
    if not prefix:
        raise ValueError("empty reference input")
    return prompt, prefix, ids


def reference_argmax(logits):
    if len(logits) != len(mp.LABELS) or any(not math.isfinite(v) for v in logits):
        raise ValueError("reference requires five finite candidate logits")
    winner = 0
    for i in range(1, len(logits)):
        if logits[i] > logits[winner]:
            winner = i
    return mp.LABELS[winner]


class ReferenceModel:
    """A second raw forward over independently encoded IDs, sharing only frozen weights/tokenizer."""

    def __init__(self, adapter):
        self.adapter = adapter

    @property
    def metadata(self):
        return {**self.adapter.metadata, "diagnostic_scorer": "independent_raw_forward_v1"}

    def score_choices(self, messages, *, labels):
        import torch

        if tuple(labels) != mp.LABELS:
            raise ValueError("reference diagnostic labels must be A-E")
        prompt, prefix, ids = reference_tokens(self.adapter._tokenizer, messages, labels)
        if len(prefix) + 1 > self.adapter._context_limit:
            raise ValueError("reference context overflow; no truncation")
        vocab = self.adapter._model.get_output_embeddings().weight.shape[0]
        if any(not 0 <= i < vocab for i in ids):
            raise ValueError("reference label outside output vocabulary")
        inputs = torch.tensor([prefix], dtype=torch.long, device=self.adapter.config.device)
        mask = torch.ones_like(inputs)
        sync = (lambda: torch.cuda.synchronize()) if self.adapter.config.device == "cuda" else lambda: None
        sync()
        started = time.perf_counter()
        with torch.inference_mode():
            scores = self.adapter._model(input_ids=inputs, attention_mask=mask, use_cache=False).logits
        sync()
        elapsed = time.perf_counter() - started
        if tuple(scores.shape) != (1, len(prefix), vocab):
            raise ValueError("invalid reference logits shape")
        logits = [float(scores[0, -1, i].item()) for i in ids]
        top = int(scores[0, -1].argmax().item())
        return Generation(reference_argmax(logits), len(prefix), 1, elapsed, {
            "labels": list(labels), "label_token_ids": ids, "candidate_logits": logits,
            "rendered_prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "input_ids_sha256": mp.digest(prefix), "scoring_evidence": "independent_raw_forward",
            "full_vocab_argmax_id": top,
            "full_vocab_argmax_text": self.adapter._tokenizer.decode([top]),
            "latency_scope": "synchronized_forward_excludes_tokenization_transfer_selection"})


def compare_scores(production, reference):
    left, right = production.metadata, reference.metadata
    fields = ("label_token_ids", "rendered_prompt_sha256")
    a, b = left.get("candidate_logits", []), right.get("candidate_logits", [])
    for values in (a, b):
        reference_argmax(values)
    return (production.input_tokens == reference.input_tokens
            and all(left.get(k) is not None and left.get(k) == right.get(k) for k in fields)
            and production.text == reference.text == reference_argmax(a) == reference_argmax(b)
            and all(math.isclose(x, y, rel_tol=0, abs_tol=LOGIT_ATOL) for x, y in zip(a, b)))


def parse_generated(text):
    match = re.fullmatch(r"([A-E])\.?", text.strip())
    return match[1] if match else None


def preflight(entries, tokenizer, vocab_size, *, evidence="scripted_tokenizer_fixture"):
    from .transformers_model import validate_choice_tokens

    prompts = {}
    for case in entries:
        key = case["prompt_sha256"]
        if key in prompts:
            continue
        prompt, prefix, ids = reference_tokens(tokenizer, _messages(case))
        if tuple(ids) != validate_choice_tokens(tokenizer, prompt, mp.LABELS, vocab_size):
            raise ValueError("production/reference label tokenization differs")
        if len(prefix) + GENERATION_CAP > 8192:
            raise ValueError("diagnostic context overflow; no truncation")
        prompts[key] = {"input_tokens": len(prefix), "label_token_ids": ids,
                        "input_ids_sha256": mp.digest(prefix),
                        "rendered_prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()}
    return {"evidence": evidence, "prompts": prompts,
            "template_sha256": hashlib.sha256(tokenizer.chat_template.encode()).hexdigest()}


def load_models(manifest, entries, output):
    """Real boundary, called only after CLI authorization; reuse the known cached runtime."""
    from . import transformers_model as tm

    os.environ.update(transport.ENV)
    config = tm.TransformersConfig(revision=mp.MODEL_REVISION, dtype="float16", device="cuda",
        context_limit=8192, action_max_new_tokens=GENERATION_CAP, memory_max_new_tokens=1024,
        generation_seed=0, local_files_only=True)
    cache = Path("/cache/huggingface/hub/models--Qwen--Qwen3-4B-Instruct-2507/snapshots") / mp.MODEL_REVISION
    runtime, cfg = transport.runtime_and_cache(tm, config, cache)
    transport.save(output / "runtime-cache.json", runtime)
    tokenizer = transport.cached_tokenizer(cache)
    checked = preflight(entries, tokenizer, cfg["vocab_size"], evidence="actual_cached_tokenizer")
    if checked["template_sha256"] != "64f85b198065d0fba2a81f37e10ed68161ce2c19a754c7100e67e0ca2ee9c326":
        raise ValueError("historical Qwen chat template differs")
    if len(checked["prompts"]) != manifest["unique_prompts"]:
        raise ValueError("preflight prompt coverage differs")
    transport.save(output / "tokenizer-preflight.json", checked)
    model = tm.TransformersModel(config)  # One load; reference shares these weights.
    transport.save(output / "model.json", model.metadata)
    return model, ReferenceModel(model)


def run(package, output, *, loader, clock=time.monotonic):
    """Run the frozen finite diagnostic. Tests inject explicitly synthetic models."""
    manifest, entries = verify_package(package, source=Path(__file__).resolve().parents[1])
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    started = clock()
    transport.save(output / "entry.json", {"manifest": manifest, "started_monotonic": started})
    transport.save(output / "cases.json", entries)
    context, requests, sequence, cache = {}, 0, 0, {}
    original_error = None
    status = {"complete": False, "manifest_sha256": manifest["manifest_sha256"]}
    with (output / "events.jsonl").open("x") as events, (output / "assessments.jsonl").open("x") as rows:
        def emit(event, **data):
            nonlocal sequence
            mp._write_line(events, {"event": event, "sequence": sequence, **context, **data})
            sequence += 1

        def before_call(method, case):
            nonlocal requests
            if clock() - started >= SOFT_SECONDS:
                raise TimeoutError("diagnostic deadline before request")
            if requests >= manifest["request_ceiling"]:
                raise RuntimeError("diagnostic request ceiling")
            context.update(method=method, case_id=case["case_id"], request_id=requests)
            requests += 1

        def assess(case, method, result, source, reused):
            label = parse_generated(result.text) if method == "generated" else result.text
            if method != "generated" and label not in mp.LABELS:
                raise ValueError("scorer returned an invalid label")
            destination = case["options"][mp.LABELS.index(label)] if label else None
            mp._write_line(rows, {k: v for k, v in case.items() if k not in {"messages", "memory"}} | {
                "method": method, "source_request_id": source, "reused": reused,
                "selected_letter": label, "selected_destination": destination,
                "correct": destination == case["gold"], "unparseable": label is None,
                "raw_answer": result.text, "finish_reason": result.metadata.get("finish_reason"),
                "option_mapping": dict(zip(mp.LABELS, case["options"]))})

        try:
            model, reference = loader(manifest, entries, output)
            status["model_is_fake"] = model.metadata.get("is_fake") is not False
            status["reference_is_fake"] = reference.metadata.get("is_fake") is not False
            logged = _LoggedModel(model, emit, lambda: requests - 1)
            other = _LoggedModel(reference, emit, lambda: requests - 1)
            for case in entries:
                key = case["prompt_sha256"]
                reused = key in cache
                if not reused:
                    results, sources = {}, {}
                    for method in METHODS:
                        before_call(method, case)
                        sources[method] = requests - 1
                        if method == "generated":
                            result = logged.generate(_messages(case), purpose="reader_diagnostic_generation")
                        else:
                            result = (logged if method == "restricted" else other).score_choices(
                                _messages(case), labels=mp.LABELS)
                        results[method] = result
                        assess(case, method, result, sources[method], False)
                        if method == "reference" and not compare_scores(results["restricted"], result):
                            emit("scoring_mismatch", production=asdict(results["restricted"]),
                                 reference=asdict(result))
                            raise ValueError("independent scoring disagreement; inspect raw evidence")
                    cache[key] = (results, sources)
                else:
                    results, sources = cache[key]
                    for method, result in results.items():
                        assess(case, method, result, sources[method], True)
            status.update(complete=True, outcome="diagnostic_complete", usage_complete=True,
                          usage={"production": logged.by_purpose, "reference": other.by_purpose})
        except BaseException as error:
            original_error = error
            status.update(outcome="error", error_type=type(error).__name__, error=str(error),
                          traceback=traceback.format_exc(), usage_complete=False)
            raise
        finally:
            try:
                events.flush(); os.fsync(events.fileno())
                rows.flush(); os.fsync(rows.fileno())
                status.update(attempted_requests=requests, wall_seconds=clock() - started)
                transport.save(output / "status.json", status)
            except BaseException as cleanup:
                if original_error is None:
                    raise
                original_error.add_note(f"Saving diagnostic evidence also failed: {cleanup!r}")
    transport.save(output / "completion.json", {p.name: mp.file_sha256(p)
                   for p in sorted(output.iterdir()) if p.is_file()})
    return report(output)


def report(output):
    """Read-only report; incomplete/error runs remain explicitly incomplete."""
    output = Path(output)
    status = _read(output / "status.json")
    if status["complete"]:
        for name, expected in _read(output / "completion.json").items():
            if mp.file_sha256(output / name) != expected:
                raise ValueError(f"diagnostic completion hash differs: {name}")
    rows = _rows(output / "assessments.jsonl")
    events = _rows(output / "events.jsonl")
    cells = {}
    for row in rows:
        key = "/".join(row[k] for k in ("method", "format", "variant"))
        cell = cells.setdefault(key, {"correct": 0, "total": 0, "unparseable": 0})
        cell["total"] += 1
        cell["correct"] += row["correct"]
        cell["unparseable"] += row["unparseable"]
    responses = [e for e in events if e["event"] == "model_response"]
    requests = {e["request_id"]: e for e in events if e["event"] == "model_request"}
    by_response = {e["request_id"]: e for e in responses}
    expected = {c["case_id"]: c for c in _read(output / "cases.json")}
    keys = [(r["case_id"], r["method"]) for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate diagnostic assessment")
    if status["complete"] and (set(keys) != {(c, m) for c in expected for m in METHODS}
            or set(requests) != set(by_response)
            or status["attempted_requests"] != len(requests)):
        raise ValueError("incomplete diagnostic coverage")
    for row in rows:
        case = expected[row["case_id"]]
        response = by_response[row["source_request_id"]]
        request = requests[row["source_request_id"]]
        label = parse_generated(response["text"]) if row["method"] == "generated" else response["text"]
        if label is not None and label not in mp.LABELS:
            raise ValueError("invalid diagnostic label")
        destination = case["options"][mp.LABELS.index(label)] if label else None
        checks = {"raw_answer": response["text"], "selected_letter": label,
                  "selected_destination": destination, "correct": destination == case["gold"],
                  "unparseable": label is None, "option_mapping": dict(zip(mp.LABELS, case["options"]))}
        if (any(row.get(k) != v for k, v in checks.items())
                or any(row.get(k) != v for k, v in case.items() if k not in {"messages", "memory"})
                or request["messages"] != case["messages"] or request["method"] != row["method"]):
            raise ValueError("diagnostic assessment disagrees with its raw request/response")
        if row["method"] != "generated" and label != reference_argmax(response["metadata"]["candidate_logits"]):
            raise ValueError("diagnostic label disagrees with raw logits")
    if status["complete"]:
        indexed = {(r["case_id"], r["method"]): r for r in rows}
        for case_id in expected:
            pair = []
            for method in ("restricted", "reference"):
                response = by_response[indexed[case_id, method]["source_request_id"]]
                pair.append(Generation(**{k: response[k] for k in
                    ("text", "input_tokens", "output_tokens", "elapsed_seconds", "metadata")}))
            if not compare_scores(*pair):
                raise ValueError("completed diagnostic contains an independent scoring disagreement")
    return {"status": status, "cells": cells, "assessments": rows,
            "physical_responses": len(responses),
            "known_input_tokens": sum(r["input_tokens"] for r in responses),
            "known_output_tokens": sum(r["output_tokens"] for r in responses),
            "known_model_seconds": sum(r["elapsed_seconds"] for r in responses),
            "limits": "selected development cases; not a new qualification or population estimate"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare", help="offline only; no tokenizer or weights")
    prep.add_argument("--output-dir", type=Path, required=True)
    prep.add_argument("--historical-unit", type=Path)
    execute = sub.add_parser("run", help="separately authorized cached A10/A10G execution only")
    execute.add_argument("--package", type=Path, required=True)
    execute.add_argument("--output-dir", type=Path, required=True)
    execute.add_argument("--authorization", type=Path, required=True)
    show = sub.add_parser("report", help="read-only; redirect outside the run directory")
    show.add_argument("directory", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.output_dir, historical_unit=args.historical_unit)
    elif args.command == "report":
        result = report(args.directory)
    else:
        manifest, _ = verify_package(args.package, source=Path(__file__).resolve().parents[1])
        if args.authorization.read_text().strip() != authorization(manifest):
            parser.error("separately supplied authorization required; template is not authorization")
        result = run(args.package, args.output_dir, loader=load_models)
    print(json.dumps(result, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
