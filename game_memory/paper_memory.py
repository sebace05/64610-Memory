"""paper-memory-v1: a three-paper, question-blind streaming notebook pilot.

Preparation and reporting are offline. Only run()'s explicit loader boundary can
load a model. Reuses the existing bounded-memory validation, repair and ledger.
"""
import argparse
from collections import Counter
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import time
import traceback
import unicodedata
import zipfile

from . import memory_probe as mp
from . import memory_probe_modal as transport
from .components import Message
from .memory import ProseMemory, StructuredMemory

VERSION = "paper-memory-v1"
DATA = "data/paper-memory-v1/papers.json"
DATA_SHA = "974ae539d780c3e31164b230da7a627d72c45d8d7d31980abe5016b55254173f"
PAPERS = ("1611.02550", "1701.08118", "1707.06939")
CONDITIONS = ("full_paper", "prose", "json", "no_context", "evidence")
BUDGET, CHUNK_CHARS = 2048, 6000
CONTEXT, WRITER_CAP, READER_CAP = 16384, 2560, 96
SOFT_SECONDS, EXECUTION_SECONDS = 1500, 1800
GPU = "NVIDIA A10G"
ABSTAIN = "INSUFFICIENT_INFORMATION"
SOURCE_FILES = (*mp.SOURCE_FILES, "game_memory/memory_probe_modal.py",
                "game_memory/paper_memory.py", "tests/test_paper_memory.py",
                "docs/paper-memory-v1.md", DATA)
WRITER_INSTRUCTION = """Read the supplied new part of a research paper and replace your notebook.
Use only the previous notebook and the new paper text supplied in this request.
Preserve useful explicit facts from all parts read so far, including exact names,
numbers, units, datasets, methods and experimental results with their qualifiers.
Choose broad factual coverage. Do not invent facts or fill missing formulas or
tables. You will not see earlier paper text again. There is no other persistent
notebook. Future questions are not supplied. Compress or omit as needed: the
complete replacement notebook, including every key and formatting token, must fit
the stated stored-memory token allowance. Return only the replacement notebook,
without commentary or code fences."""
READER_INSTRUCTION = f"""Answer a factual question using only the supplied context.
Return the shortest answer that identifies the requested fact, preferably just
the name or number. Do not explain. Preserve numeric values and units. If the
context does not supply the answer, return exactly {ABSTAIN}."""


def settings():
    return dict(version=VERSION, allowance=BUDGET, chunk_char_limit=CHUNK_CHARS,
                context_limit=CONTEXT, writer_generation_cap=WRITER_CAP,
                reader_generation_cap=READER_CAP, soft_seconds=SOFT_SECONDS,
                execution_seconds=EXECUTION_SECONDS, gpu=GPU,
                conditions=list(CONDITIONS), model=dict(id=mp.MODEL_ID,
                revision=mp.MODEL_REVISION, dtype="float16", generation_seed=0))


@dataclass(frozen=True)
class PaperContext:
    memory_token_limit: int = BUDGET


class _PaperWriter:
    @property
    def metadata(self):
        return {**super().metadata, "prompt_version": VERSION + "/writer-v1"}

    def _messages(self, previous_rendered, action, observation, context, limit):
        return (Message("system", "Paper notebook writer " + VERSION + "/writer-v1\n"
                        + WRITER_INSTRUCTION + "\n\nRequired format:\n" + self.format_instructions),
                Message("user", json.dumps(dict(previous_memory=previous_rendered,
                        chunk=observation, memory_token_limit=limit),
                        sort_keys=True, ensure_ascii=False)))


class PaperProseMemory(_PaperWriter, ProseMemory):
    pass


class PaperJSONMemory(_PaperWriter, StructuredMemory):
    pass


WRITERS = dict(prose=PaperProseMemory, json=PaperJSONMemory)


def blocks(paper):
    return ["Title: " + paper["title"], "Abstract: " + paper["abstract"],
            *[f"[Paragraph {i}; {p['section']}]\n{p['text']}"
              for i, p in enumerate(paper["paragraphs"])]]


def chunks(paper):
    """Pack whole paragraphs in source order; never truncate an oversized one."""
    result, current = [], ""
    for block in blocks(paper):
        candidate = current + ("\n\n" if current else "") + block
        if current and len(candidate) > CHUNK_CHARS:
            result.append(current)
            current = block
        else:
            current = candidate
    if current:
        result.append(current)
    return result


def full_text(paper):
    return "\n\n".join(blocks(paper))


def reader_messages(context, question):
    return (Message("system", "Paper fact reader " + VERSION + "/reader-v1\n" + READER_INSTRUCTION),
            Message("user", f"Context:\n{context}\n\nQuestion:\n{question}"))


def normalize(text):
    text = unicodedata.normalize("NFKC", text).strip().casefold()
    text = re.sub(r"^answer:\s*", "", text)
    text = re.sub(r"(?<=\d),(?=\d)", "", text)
    for _ in range(2):  # Permit a terminal period inside or outside outer quotes.
        text = text.strip('"\'“”‘’')
        if text.endswith("."):
            text = text[:-1]
    return " ".join(text.split())


def grade(answer, aliases):
    prediction = normalize(answer)
    exact, f1 = False, 0.0
    for alias in aliases:
        target = normalize(alias)
        exact |= prediction == target
        a, b = Counter(prediction.split()), Counter(target.split())
        overlap = sum((a & b).values())
        if overlap:
            f1 = max(f1, 2 * overlap / (sum(a.values()) + sum(b.values())))
    return dict(normalized_answer=prediction, correct=exact, token_f1=f1,
                abstained=prediction == normalize(ABSTAIN), empty_answer=not prediction)


def validate_data(data):
    if data.get("version") != VERSION or type(data.get("is_fake")) is not bool:
        raise ValueError("paper data version/provenance missing")
    papers = data["papers"]
    mp._require_exact([p["paper_id"] for p in papers], ["P00", "P01", "P02"], "papers")
    if not data["is_fake"] and tuple(p["qasper_id"] for p in papers) != PAPERS:
        raise ValueError("real paper selection differs")
    for paper in papers:
        if not paper["title"] or not paper["abstract"] or not paper["paragraphs"]:
            raise ValueError("paper text missing")
        mp._require_exact([q["question_id"] for q in paper["questions"]],
                          [paper["paper_id"] + f"/Q{i}" for i in range(3)], "questions")
        for q in paper["questions"]:
            evidence = paper["paragraphs"][q["evidence_index"]]["text"]
            if (q["evidence_text"] != evidence or q["gold_anchor"] not in evidence
                    or not q["aliases"] or q["gold_anchor"] not in q["aliases"]
                    or any(not isinstance(a, str) or not a.strip() for a in q["aliases"])):
                raise ValueError("gold answer/evidence differs from source")
    return papers


def prepare(output, data_path=None):
    root = Path(__file__).resolve().parents[1]
    data_path = Path(data_path) if data_path else root / DATA
    data = transport.read(data_path)
    papers = validate_data(data)
    if not data["is_fake"] and mp.file_sha256(data_path) != DATA_SHA:
        raise ValueError("curated real data bytes differ")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(data_path, output / "papers.json")
    transport.save(output / "chunks.json", {p["paper_id"]: chunks(p) for p in papers})
    with zipfile.ZipFile(output / "source.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in SOURCE_FILES:
            archive.write(root / name, name)
    manifest = dict(**settings(), is_fake=data["is_fake"],
        papers=[dict(paper_id=p["paper_id"], qasper_id=p["qasper_id"],
                     chunk_count=len(chunks(p)), primary_reader_calls=15,
                     repeat_calls=5, request_ceiling=4 * len(chunks(p)) + 20) for p in papers],
        files={p.name: mp.file_sha256(p) for p in sorted(output.iterdir())},
        source_files={n: mp.file_sha256(root / n) for n in SOURCE_FILES})
    manifest["manifest_sha256"] = mp.digest(manifest)
    transport.save(output / "manifest.json", manifest)
    return manifest


def verify_package(package, source=None):
    package = Path(package)
    manifest = transport.read(package / "manifest.json")
    if (manifest["manifest_sha256"] != mp.digest({k: v for k, v in manifest.items() if k != "manifest_sha256"})
            or any(manifest.get(k) != v for k, v in settings().items())):
        raise ValueError("paper manifest/settings differ")
    mp._require_exact(list(manifest["files"]), [str(p.relative_to(package)) for p in package.rglob('*')
                      if p.is_file() and p.name != "manifest.json"], "package files")
    for name, expected in manifest["files"].items():
        if Path(name).is_absolute() or ".." in Path(name).parts or mp.file_sha256(package / name) != expected:
            raise ValueError("package path/bytes differ")
    with zipfile.ZipFile(package / "source.zip") as archive:
        mp._require_exact(archive.namelist(), list(SOURCE_FILES), "source archive")
        if set(manifest["source_files"]) != set(SOURCE_FILES):
            raise ValueError("source inventory differs")
        for name, expected in manifest["source_files"].items():
            if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                raise ValueError("archived source differs")
            if source is not None and mp.file_sha256(Path(source) / name) != expected:
                raise ValueError("current source differs: " + name)
    data = transport.read(package / "papers.json")
    papers = validate_data(data)
    if (data["is_fake"] != manifest["is_fake"] or
            (not data["is_fake"] and mp.file_sha256(package / "papers.json") != DATA_SHA)):
        raise ValueError("real/fake paper provenance differs")
    if transport.read(package / "chunks.json") != {p["paper_id"]: chunks(p) for p in papers}:
        raise ValueError("frozen chunks differ")
    expected = [dict(paper_id=p["paper_id"], qasper_id=p["qasper_id"], chunk_count=len(chunks(p)),
                     primary_reader_calls=15, repeat_calls=5, request_ceiling=4 * len(chunks(p)) + 20)
                for p in papers]
    if manifest["papers"] != expected:
        raise ValueError("paper call ceilings differ")
    return manifest, papers


def prompt_tokens(tokenizer, messages):
    text = tokenizer.apply_chat_template([asdict(m) for m in messages],
                                         tokenize=False, add_generation_prompt=True)
    return len(tokenizer.encode(text, add_special_tokens=False))


def preflight(paper, tokenizer):
    checks = []
    for q in paper["questions"]:
        for name, text in (("full_paper", full_text(paper)), ("evidence", q["evidence_text"]),
                           ("no_context", "")):
            n = prompt_tokens(tokenizer, reader_messages(text, q["question"]))
            checks.append(dict(condition=name, question_id=q["question_id"], input_tokens=n,
                               reserved_output=READER_CAP, conservative_total=n + READER_CAP))
    for fmt, cls in WRITERS.items():
        writer = cls()
        for i, chunk in enumerate(chunks(paper)):
            n = prompt_tokens(tokenizer, writer._messages(writer.empty(), "", chunk, PaperContext(), BUDGET))
            # A count of the empty prompt alone does not bound arbitrary UTF-8
            # serialization. Actual populated and repair prompts are checked too.
            checks.append(dict(format=fmt, chunk_index=i, input_tokens=n,
                               reserved_output=WRITER_CAP,
                               conservative_total=n + BUDGET + 2 * WRITER_CAP + 512))
    if any(c["conservative_total"] > CONTEXT for c in checks):
        raise ValueError("paper prompts exceed preflight context headroom")
    return dict(evidence="actual_cached_tokenizer", source_tokens=len(tokenizer.encode(full_text(paper),
                add_special_tokens=False)), chunk_tokens=[len(tokenizer.encode(c, add_special_tokens=False))
                for c in chunks(paper)], checks=checks,
                note="headroom heuristic; every actual prompt is checked without truncation before inference")


def load_model(manifest, paper, output):
    if manifest["is_fake"]:
        raise ValueError("real loader refuses fake papers before weights")
    from . import transformers_model as tm
    os.environ.update(transport.ENV)
    config = tm.TransformersConfig(revision=mp.MODEL_REVISION, dtype="float16", device="cuda",
                context_limit=CONTEXT, action_max_new_tokens=READER_CAP,
                memory_max_new_tokens=WRITER_CAP, generation_seed=0, local_files_only=True)
    cache = Path("/cache/huggingface/hub/models--Qwen--Qwen3-4B-Instruct-2507/snapshots") / mp.MODEL_REVISION
    runtime, cfg = transport.runtime_and_cache(tm, config, cache)
    transport.save(output / "runtime-cache.json", runtime)
    if runtime["runtime"]["gpu"] != GPU or cfg["max_position_embeddings"] < CONTEXT:
        raise ValueError("pinned device/context required before tokenizer/weights")
    tokenizer = transport.cached_tokenizer(cache)
    transport.save(output / "tokenizer-preflight.json", preflight(paper, tokenizer))
    model = tm.TransformersModel(config)
    transport.save(output / "model.json", model.metadata)
    return model


class _LimitedModel:
    def __init__(self, model, ceiling, deadline, clock):
        self.model, self.ceiling, self.deadline, self.clock = model, ceiling, deadline, clock
        self.calls = 0

    @property
    def metadata(self):
        return self.model.metadata

    def count_tokens(self, text):
        return self.model.count_tokens(text)

    def generate(self, messages, *, purpose):
        if self.calls >= self.ceiling or self.clock() > self.deadline:
            raise mp.StageTimeout("paper request ceiling/deadline reached before delegation")
        cap = READER_CAP if purpose == "action" else WRITER_CAP
        tokenizer = getattr(self.model, "_tokenizer", None)
        reference = prompt_tokens(tokenizer, messages) if tokenizer is not None else None
        if reference is not None and reference + cap > CONTEXT:
            raise ValueError("actual paper prompt over context; not truncated")
        self.calls += 1
        result = self.model.generate(messages, purpose=purpose)
        return replace(result, metadata={**result.metadata, "reference_input_tokens": reference,
                       "messages_sha256": mp.digest([asdict(m) for m in messages])})


def _recounts(model, texts):
    tokenizer = getattr(model, "_tokenizer", None)
    return dict(evidence="independent_cached_tokenizer" if tokenizer is not None else "fake_counter",
                counts={hashlib.sha256(t.encode()).hexdigest(): (len(tokenizer.encode(t, add_special_tokens=False))
                        if tokenizer is not None else model.count_tokens(t)) for t in set(texts)})


def _sync(unit, commit):
    for handle in unit.files.values():
        handle.flush()
        os.fsync(handle.fileno())
    commit()


def run(package, output, paper_id, *, loader=load_model, commit=lambda: None, clock=time.monotonic):
    manifest, papers = verify_package(package, Path(__file__).resolve().parents[1])
    paper = next(p for p in papers if p["paper_id"] == paper_id)
    ceiling = next(p["request_ceiling"] for p in manifest["papers"] if p["paper_id"] == paper_id)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    started = clock()
    shutil.copytree(package, output / "inputs")
    transport.save(output / "entry.json", dict(paper_id=paper_id, manifest=manifest))
    commit()
    status = dict(complete=False, paper_id=paper_id, manifest_sha256=manifest["manifest_sha256"])
    original, unit, limited = None, None, None
    try:
        model = loader(manifest, paper, output)
        status["model_is_fake"] = model.metadata.get("is_fake") is not False
        limited = _LimitedModel(model, ceiling, started + SOFT_SECONDS, clock)
        notes = {}
        for fmt, cls in WRITERS.items():
            writer = cls()
            state = writer.empty()
            texts = [state]
            unit = mp._Unit(output / fmt, limited, started + SOFT_SECONDS, clock)
            for i, chunk in enumerate(chunks(paper)):
                unit.context = dict(step=i, role="writer", paper_id=paper_id, format=fmt, chunk_index=i)
                unit.counter.counts = []
                first = unit.request_id + 1
                result = writer.update(state, "", chunk, PaperContext(), unit.logged)
                mp._write_line(unit.files["writes.jsonl"], dict(chunk_index=i, previous_state=state,
                    state=result.memory, rendered=writer.render(result.memory),
                    update_events=list(result.events), request_ids=list(range(first, unit.request_id + 1)),
                    token_counts=unit.counter.counts))
                state = result.memory
                texts.extend([state, *[e["text"] for e in mp._jsonl(unit.dir / "events.jsonl")
                    if e["event"] == "model_response" and mp._candidate(fmt, e["text"])[0] is not None]])
                # Include canonical JSON candidates in independent storage recounts.
                texts.extend([mp._candidate(fmt, e["text"])[0] for e in mp._jsonl(unit.dir / "events.jsonl")
                    if e["event"] == "model_response" and mp._candidate(fmt, e["text"])[0] is not None])
                _sync(unit, commit)
            notes[fmt] = writer.render(state)
            unit.complete(dict(format=fmt, final_memory=notes[fmt], stored_tokens=model.count_tokens(notes[fmt]),
                               model=model.metadata, recounts=_recounts(model, texts)), commit)
            unit = None
            audit_writer(output / fmt, paper, real=not status["model_is_fake"])
        unit = mp._Unit(output / "reader", limited, started + SOFT_SECONDS, clock)
        jobs = [(c, q, "primary") for c in CONDITIONS for q in paper["questions"]]
        jobs += [(c, paper["questions"][0], "repeat") for c in CONDITIONS]
        for i, (condition, q, method) in enumerate(jobs):
            context = (full_text(paper) if condition == "full_paper" else
                       q["evidence_text"] if condition == "evidence" else
                       "" if condition == "no_context" else notes[condition])
            unit.context = dict(step=i, role="reader", paper_id=paper_id, condition=condition,
                                question_id=q["question_id"], method=method)
            result = unit.logged.generate(reader_messages(context, q["question"]), purpose="action")
            mp._write_line(unit.files["assessments.jsonl"], dict(condition=condition,
                question_id=q["question_id"], method=method, source_request_id=unit.request_id,
                answer=result.text, **grade(result.text, q["aliases"])))
            _sync(unit, commit)
        unit.complete(dict(model=model.metadata), commit)
        unit = None
        audit_reader(output / "reader", paper, notes, real=not status["model_is_fake"])
        status["complete"] = True
    except BaseException as error:
        original = error
        status.update(error=repr(error), traceback=traceback.format_exc())
        raise
    finally:
        if unit is not None:
            unit.close()
        status.update(end_to_end_seconds=clock() - started, delegated_calls=limited.calls if limited else 0)
        try:
            transport.save(output / "status.json", status)
            commit()
        except BaseException as cleanup:
            if original is None:
                raise
            original.add_note(f"Persisting status also failed: {cleanup!r}")
    return report(output)


def _audit_events(directory, *, real):
    mp.verify_completion(directory)
    events = mp._jsonl(directory / "events.jsonl")
    if [e["sequence"] for e in events] != list(range(len(events))):
        raise mp.AuditError("event sequence differs")
    requests = [e for e in events if e["event"] == "model_request"]
    responses = [e for e in events if e["event"] == "model_response"]
    if (len(events) != 2 * len(requests) or len(requests) != len(responses)
            or [e["request_id"] for e in requests] != list(range(len(requests)))
            or [e["request_id"] for e in responses] != list(range(len(requests)))
            or any(events[2*i] != r or events[2*i+1] != responses[i] for i, r in enumerate(requests))):
        raise mp.AuditError("incomplete/duplicate physical event coverage")
    for request, response in zip(requests, responses):
        if request["purpose"] != response["purpose"]:
            raise mp.AuditError("response purpose differs")
        if real:
            meta = response["metadata"]
            cap = READER_CAP if request["purpose"] == "action" else WRITER_CAP
            if (meta.get("do_sample") is not False or meta.get("num_beams") != 1
                    or meta.get("use_model_defaults") is not False or meta.get("max_new_tokens") != cap
                    or meta.get("reference_input_tokens") != response["input_tokens"]
                    or meta.get("messages_sha256") != mp.digest(request["messages"])
                    or response["input_tokens"] + cap > CONTEXT):
                raise mp.AuditError("actual greedy prompt/token evidence differs")
    summary = transport.read(directory / "summary.json")
    if real and (summary["model"].get("is_fake") is not False or summary["model"].get("gpu") != GPU
                 or summary["model"].get("revision") != mp.MODEL_REVISION):
        raise mp.AuditError("actual pinned model missing")
    return requests, responses, summary


def audit_writer(directory, paper, *, real):
    directory = Path(directory)
    requests, responses, summary = _audit_events(directory, real=real)
    fmt = directory.name
    writer = WRITERS[fmt]()
    recounts = summary["recounts"]
    if real and recounts["evidence"] != "independent_cached_tokenizer":
        raise mp.AuditError("independent memory recount missing")
    def count(text):
        return dict(text_sha256=hashlib.sha256(text.encode()).hexdigest(),
                    count=recounts["counts"][hashlib.sha256(text.encode()).hexdigest()])
    writes = mp._jsonl(directory / "writes.jsonl")
    if len(writes) != len(chunks(paper)) or mp._jsonl(directory / "assessments.jsonl"):
        raise mp.AuditError("writer chain coverage differs")
    state, cursor = writer.empty(), 0
    for i, (write, chunk) in enumerate(zip(writes, chunks(paper))):
        messages = writer._messages(state, "", chunk, PaperContext(), BUDGET)
        counts, update_events, ids, accepted = [count(state)], [], [], False
        for attempt in range(2):
            purpose = "memory_repair" if attempt else "memory"
            request, response = requests[cursor], responses[cursor]
            expected = [asdict(m) for m in messages]
            if (request["messages"] != expected or request["purpose"] != purpose
                    or request.get("chunk_index") != i or request.get("format") != fmt
                    or request.get("paper_id") != paper["paper_id"]):
                raise mp.AuditError("writer prompt/provenance differs")
            ids.append(cursor)
            cursor += 1
            candidate, reason = mp._candidate(fmt, response["text"])
            if candidate is not None:
                counts.append(count(candidate))
                if counts[-1]["count"] > BUDGET:
                    reason = f"over_budget:{counts[-1]['count']}>{BUDGET}"
            if reason is None:
                if candidate != response["text"]:
                    update_events.append(purpose + "_json_canonicalized")
                update_events.append(purpose + "_accepted")
                accepted = True
                break
            update_events.append(purpose + "_rejected:" + reason)
            messages = (*messages, Message("assistant", response["text"]),
                        Message("user", mp.REPAIR_INSTRUCTION.format(reason=reason, limit=BUDGET)))
        if not accepted:
            candidate = state
            update_events.append("memory_fallback:previous_valid_memory")
        expected_write = dict(chunk_index=i, previous_state=state, state=candidate,
                rendered=candidate, update_events=update_events, request_ids=ids, token_counts=counts)
        if write != expected_write:
            raise mp.AuditError("stored notebook/repair/count replay differs")
        state = candidate
    if cursor != len(requests) or summary["final_memory"] != state or summary["stored_tokens"] != count(state)["count"]:
        raise mp.AuditError("final notebook/physical coverage differs")
    return state


def audit_reader(directory, paper, notes, *, real):
    directory = Path(directory)
    requests, responses, _ = _audit_events(directory, real=real)
    rows = mp._jsonl(directory / "assessments.jsonl")
    jobs = [(c, q, "primary") for c in CONDITIONS for q in paper["questions"]]
    jobs += [(c, paper["questions"][0], "repeat") for c in CONDITIONS]
    if len(rows) != 20 or len(requests) != 20 or mp._jsonl(directory / "writes.jsonl"):
        raise mp.AuditError("reader coverage differs")
    for i, ((condition, q, method), row, request, response) in enumerate(zip(jobs, rows, requests, responses)):
        context = (full_text(paper) if condition == "full_paper" else
                   q["evidence_text"] if condition == "evidence" else
                   "" if condition == "no_context" else notes[condition])
        if (request["messages"] != [asdict(m) for m in reader_messages(context, q["question"])]
                or request["purpose"] != "action" or request.get("paper_id") != paper["paper_id"]
                or any(request.get(k) != v for k, v in dict(condition=condition,
                       question_id=q["question_id"], method=method).items())
                or row != dict(condition=condition, question_id=q["question_id"], method=method,
                               source_request_id=i, answer=response["text"], **grade(response["text"], q["aliases"]))):
            raise mp.AuditError("reader prompt/grading replay differs")
    return rows


def report(output):
    output = Path(output)
    manifest, papers = verify_package(output / "inputs")
    status = transport.read(output / "status.json")
    paper = next(p for p in papers if p["paper_id"] == status["paper_id"])
    ceiling = next(p["request_ceiling"] for p in manifest["papers"] if p["paper_id"] == status["paper_id"])
    events = [e for f in output.glob("*/events.jsonl") for e in mp._jsonl(f)]
    requests = [e for e in events if e["event"] == "model_request"]
    responses = [e for e in events if e["event"] == "model_response"]
    usage = dict(requests=len(requests), responses=len(responses), unknown_usage_requests=len(requests)-len(responses),
        input_tokens=sum(e["input_tokens"] for e in responses), output_tokens=sum(e["output_tokens"] for e in responses),
        inference_seconds=sum(e["elapsed_seconds"] for e in responses),
        repairs=sum(e["purpose"] == "memory_repair" for e in requests),
        calls_by_purpose=dict(Counter(e["purpose"] for e in requests)),
        time_by_purpose={p: sum(e["elapsed_seconds"] for e in responses if e["purpose"] == p)
                         for p in sorted({e["purpose"] for e in responses})})
    result = dict(status=status, known_usage=usage, request_ceiling=ceiling)
    if not status["complete"]:
        return result
    real = not status["model_is_fake"]
    notes = {fmt: audit_writer(output / fmt, paper, real=real) for fmt in WRITERS}
    rows = audit_reader(output / "reader", paper, notes, real=real)
    if (usage["requests"] > ceiling or usage["unknown_usage_requests"] or
            status["delegated_calls"] != usage["requests"] or
            status["manifest_sha256"] != manifest["manifest_sha256"]):
        raise mp.AuditError("physical budget/status differs")
    primary = [r for r in rows if r["method"] == "primary"]
    result.update(metrics={c: dict(correct=sum(r["correct"] for r in primary if r["condition"] == c), total=3,
                    token_f1=sum(r["token_f1"] for r in primary if r["condition"] == c)/3,
                    abstentions=sum(r["abstained"] for r in primary if r["condition"] == c)) for c in CONDITIONS},
                  rows=rows, repeat_disagreements=[r for r in rows if r["method"] == "repeat" and
                    r["answer"] != next(p["answer"] for p in primary if p["condition"] == r["condition"]
                                         and p["question_id"] == r["question_id"])],
                  stored_tokens={fmt: transport.read(output / fmt / "summary.json")["stored_tokens"] for fmt in WRITERS})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("output", type=Path)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("package", type=Path)
    run_parser.add_argument("output", type=Path)
    run_parser.add_argument("--paper", choices=("P00", "P01", "P02"), required=True)
    rep = sub.add_parser("report")
    rep.add_argument("output", type=Path)
    args = parser.parse_args()
    result = (prepare(args.output) if args.action == "prepare" else
              run(args.package, args.output, args.paper) if args.action == "run" else report(args.output))
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
