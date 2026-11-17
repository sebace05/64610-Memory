"""memory-probe-v1: controlled prose/JSON memory probe (docs/memory-probe-v1.md).

Fixed public transcripts with counterfactual sibling worlds isolate retained memory
from action competence. Writers reuse the p1 bounded-memory validation, one repair,
and previous-state fallback through the _messages hook; the reader is one restricted
label argmax. Model calls go through runner._LoggedModel. Real models are built only
by a separately authorized Modal worker; this module never constructs one.
"""

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import random
import time
import traceback
import zipfile

from .components import Message
from .memory import ProseMemory, StructuredMemory, _object, _serialize, _text, _InvalidMemory
from .runner import _LoggedModel

PROTOCOL = "memory-probe-v1"
WRITER_VERSION = "probe-writer-v1"
READER_VERSION = "probe-reader-v1"
GLOBAL_SEED = 0
DESTINATIONS = ("amber", "blue", "green", "violet")
ABSTAIN = "insufficient information"
LABELS = ("A", "B", "C", "D", "E")
FILLERS = 12
PROBES = {"P0": 1, "P12": 13}  # probe -> index of the last observation written
HIGH = 256
PILOT_LOW = 64
FLOOR_LOW = 128
FORMATS = ("prose", "json")
INITIAL, UPDATE = "[INITIAL_OBSERVATION]", "[PUBLIC_UPDATE]"
SPLITS = {"dev": ("D", 2), "qualification": ("Q", 4), "test": ("T", 8)}
MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"
MODEL_REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"

PUBLIC_RULES = """1. An assignment remains valid until a later explicit assignment update or revocation.
2. An assignment update states the current destination and supersedes the earlier record. It may repeat the same destination. Revocation means the current destination is unknown; an old assignment must not be reused.
3. Any entity may be queried later. The query is not disclosed during writing.
4. No record lookup, reread, or other information source is available at query time. Choose "insufficient information" when the supplied evidence does not justify a destination. This is abstention, not a successful information-recovery action."""

READER_INSTRUCTION = ("Use only the supplied context and current query. Assignments persist until "
    "explicitly replaced or revoked; destinations may repeat. Choose the latest supported "
    "destination of the queried entity. If the assignment is absent, revoked, or unresolved, "
    "choose insufficient information. Do not infer a destination from the other entities or "
    "guess. In diagnostic notes, a JSON null denotes an unknown destination; an omitted entity "
    "supplies no assignment. The context may be public history, prose, or JSON. Return only "
    "the label of one listed option.")

WRITER_INSTRUCTION = ("Maintain the latest confirmed assignment of every observed entity. Replace "
    "superseded assignments and distinguish revoked or unknown assignments from confirmed "
    "destinations. Destinations may repeat. Any entity may be queried later. Use only previous "
    "memory, the last event, and the new public observation. Do not invent assignments or "
    "retain irrelevant pulse descriptions. Your replacement is the only persistent notebook and "
    "its complete rendering must fit the stated token allowance.")

# Generated names must not collide with task vocabulary or option labels.
RESERVED = frozenset({*DESTINATIONS, "pulse", "ambient", "insufficient", "information",
                      "assignment", "update", "revoked", "unknown", "a", "b", "c", "d", "e"})
WRITER_FIELDS = frozenset({"previous_memory", "last_event", "observation", "public_rules",
                           "memory_token_limit"})
PRIMARY_CONTEXTS = ("full_history", "no_memory", "sufficient_prose", "sufficient_json")
QUALIFICATION_CONTEXTS = ("full_history", "sufficient_prose", "sufficient_json",
                          "missing_prose", "missing_json", "no_memory")


class StageTimeout(RuntimeError):
    """The soft stage deadline expired before a model request was sent."""


class AuditError(ValueError):
    """Evidence does not reconcile; the stage or family cannot be accepted."""


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False)
                          .encode("utf-8")).hexdigest()


def stream(*purpose) -> random.Random:
    """Per-purpose RNG from SHA-256 of the protocol, global seed and purpose; never hash()."""
    key = "|".join((PROTOCOL, str(GLOBAL_SEED), *map(str, purpose)))
    return random.Random(int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big"))


# ---------------------------------------------------------------- generator

def _name(rng, used) -> str:
    consonants, vowels = "bdfgklmnprstvwxz", "aeiou"
    while True:
        name = "".join(rng.choice(consonants if i % 2 == 0 else vowels) for i in range(5))
        if name not in used and name not in RESERVED:
            used.add(name)
            return name


def _composition(family: dict) -> tuple:
    """Name-, filler- and option-free structure used for cross-split disjointness."""
    roles = family["roles"]
    others = sorted(v for n, v in family["base"].items()
                    if n not in {roles["target"], roles["updated"], roles["revoked"]})
    worlds = family["worlds"]
    return (family["query_type"], tuple(others),
            tuple(w["initial"][roles["target"]] for w in worlds),
            tuple(w["update_value"] for w in worlds),
            family["base"][roles["revoked"]], family["base"][roles["updated"]])


def _family(split: str, index: int, old_value: str | None, used: set, attempt: int) -> dict:
    rng = stream(split, index, "family", attempt)
    prefix = SPLITS[split][0]
    names = [_name(rng, used) for _ in range(8)]
    order = names[:]
    rng.shuffle(order)
    base = {n: rng.choice(DESTINATIONS) for n in names}
    updated_query = index % 2 == 0
    target = names[0]
    revoked = names[2]
    updated = target if updated_query else names[1]
    if updated_query:
        base[target] = old_value
    update_value = None if updated_query else rng.choice(DESTINATIONS)
    pulses = [_name(rng, used) for _ in range(FILLERS)]
    options = [*DESTINATIONS, ABSTAIN]
    stream(split, index, "options").shuffle(options)
    worlds = []
    for w, answer in enumerate(DESTINATIONS):
        initial = dict(base)
        if not updated_query:
            initial[target] = answer
        value = answer if updated_query else update_value
        obs0 = "Assignments: " + "; ".join(f"{n}={initial[n]}" for n in order) + "."
        obs1 = (f"Update: {updated} is now assigned to {value}, replacing its previous "
                f"assignment.\n{revoked.capitalize()}'s assignment is revoked; its destination "
                "is now unknown.")
        fillers = [f"Ambient pulse {p}. No assignments changed." for p in pulses]
        worlds.append({"world": w, "answer": answer, "initial": initial, "update_value": value,
                       "observations": [obs0, obs1, *fillers]})
    return {"family_id": f"{prefix}{index:02d}", "split": split, "index": index,
            "query_type": "updated" if updated_query else "untouched", "order": order,
            "base": base, "roles": {"target": target, "updated": updated, "revoked": revoked},
            "options": options, "labels": list(LABELS), "pulses": pulses, "worlds": worlds,
            "generation_attempt": attempt}


def generate_splits() -> dict:
    """All 14 families; old values balanced within each split's updated-query families."""
    used: set = set()
    splits, compositions = {}, {}
    for split, (_, count) in SPLITS.items():
        olds = list(DESTINATIONS)
        stream(split, "old-values").shuffle(olds)
        families = []
        for i in range(count):
            old = olds[(i // 2) % 4] if i % 2 == 0 else None
            for attempt in range(100):
                trial_used = set(used)
                family = _family(split, i, old, trial_used, attempt)
                comp = _composition(family)
                if all(comp not in c for s, c in compositions.items() if s != split):
                    used = trial_used
                    break
            else:
                raise RuntimeError("could not generate a disjoint composition")
            families.append(family)
            compositions.setdefault(split, set()).add(comp)
        splits[split] = families
    check_splits(splits)
    return splits


def check_splits(splits: dict) -> None:
    """Fail preparation on any construction, leakage or disjointness violation."""
    seen_names, comps = {}, {}
    for split, families in splits.items():
        for f in families:
            r = f["roles"]
            if len(set(f["order"])) != 8 or any(len(n) != 5 or not n.isalpha() or not n.islower()
                                                or n in RESERVED for n in f["order"]):
                raise ValueError(f"{f['family_id']}: invalid entity names")
            if r["revoked"] in {r["target"], r["updated"]}:
                raise ValueError(f"{f['family_id']}: revoked entity overlaps a query/update role")
            if (f["query_type"] == "updated") != (r["updated"] == r["target"]):
                raise ValueError(f"{f['family_id']}: update role does not match query type")
            if sorted(w["answer"] for w in f["worlds"]) != sorted(DESTINATIONS):
                raise ValueError(f"{f['family_id']}: siblings do not cover all four answers")
            if sorted(f["options"]) != sorted([*DESTINATIONS, ABSTAIN]):
                raise ValueError(f"{f['family_id']}: invalid options")
            obs = [w["observations"] for w in f["worlds"]]
            if f["query_type"] == "updated":
                if len({o[0] for o in obs}) != 1:
                    raise ValueError(f"{f['family_id']}: updated siblings differ before the update")
            elif len({o[1] for o in obs}) != 1:
                raise ValueError(f"{f['family_id']}: untouched siblings differ in the update")
            if len({tuple(o[2:]) for o in obs}) != 1:
                raise ValueError(f"{f['family_id']}: fillers differ across siblings")
            for filler in obs[0][2:]:
                words = set(filler.lower().replace(".", " ").split())
                if words & (set(f["order"]) | set(DESTINATIONS) | {"query", "destination"}):
                    raise ValueError(f"{f['family_id']}: filler contains a fact or cue")
            for n in [*f["order"], *f["pulses"]]:
                if n in RESERVED:
                    raise ValueError(f"{f['family_id']}: reserved word used as a name")
                if seen_names.setdefault(n, split) != split:
                    raise ValueError(f"name {n} shared across splits")
            comps.setdefault(split, set()).add(_composition(f))
    for a in comps:
        for b in comps:
            if a < b and comps[a] & comps[b]:
                raise ValueError(f"normalized composition shared by {a} and {b}")


# ---------------------------------------------------------------- public state and notes

def public_state(observations: list[str]) -> dict:
    """Forward reduction of public observations: entity -> destination or None (revoked)."""
    state, order = {}, []
    for text in observations:
        if text.startswith("Assignments: "):
            for item in text[len("Assignments: "):-1].split("; "):
                name, value = item.split("=")
                state[name] = value
                order.append(name)
        elif text.startswith("Update: "):
            first, second = text.split("\n")
            name, rest = first[len("Update: "):].split(" is now assigned to ")
            state[name] = rest.split(",")[0]
            state[second.split("'s assignment is revoked")[0].lower()] = None
    return {"order": order, "state": state}


def prose_note(reduced: dict, omit: str | None = None) -> str:
    parts = []
    for n in reduced["order"]:
        if n == omit:
            continue
        v = reduced["state"][n]
        parts.append(f"{n.capitalize()}'s assignment is revoked; its destination is unknown."
                     if v is None else f"{n.capitalize()} is assigned to {v}.")
    return " ".join(parts)


def json_note(reduced: dict, omit: str | None = None) -> str:
    return _serialize({n: v for n, v in reduced["state"].items() if n != omit})


def history_context(observations: list[str]) -> str:
    return json.dumps([{"last_event": INITIAL if i == 0 else UPDATE, "observation": o}
                       for i, o in enumerate(observations)], ensure_ascii=False)


# ---------------------------------------------------------------- prompts

def reader_messages(memory: str, query: str, options: list[str]) -> tuple[Message, ...]:
    lines = "\n".join(f"{label}. {option}" for label, option in zip(LABELS, options))
    return (Message("system", READER_INSTRUCTION),
            Message("user", f"Public rules:\n{PUBLIC_RULES}\n\nRetained context:\n{memory}"
                            f"\n\nCurrent query:\nWhat is {query}'s current destination?\n{lines}"))


def outside_memory(messages) -> str:
    """Reader input with the retained-context block removed (sibling identity check)."""
    user = messages[1]["content"] if isinstance(messages[1], dict) else messages[1].content
    head, rest = user.split("\nRetained context:\n", 1)
    return json.dumps([messages[0]["content"] if isinstance(messages[0], dict)
                       else messages[0].content, head, rest.split("\n\nCurrent query:\n", 1)[1]])


@dataclass(frozen=True)
class ProbeContext:
    """Writer-visible public settings; MemoryContext is unchanged."""

    public_rules: str
    memory_token_limit: int


class _ProbeWriter:
    __slots__ = ()

    def _messages(self, previous_rendered, action, observation, context, limit):
        if action not in {INITIAL, UPDATE}:
            raise ValueError("probe writer last_event must be a declared marker")
        return (
            Message("system", f"Memory writer {WRITER_VERSION}\n{WRITER_INSTRUCTION}"
                    f"\n\nRequired format:\n{self.format_instructions}"),
            Message("user", json.dumps({
                "previous_memory": previous_rendered, "last_event": action,
                "observation": observation, "public_rules": context.public_rules,
                "memory_token_limit": limit,
            }, sort_keys=True, ensure_ascii=False)),
        )

    @property
    def metadata(self) -> dict:
        data = {k: v for k, v in super().metadata.items() if k != "version"}
        data.update(implementation=type(self).__name__, prompt_version=WRITER_VERSION,
                    protocol=PROTOCOL, format_instruction_source="p1-memory-v17")
        return data


class ProbeProseMemory(_ProbeWriter, ProseMemory):
    __slots__ = ()


class ProbeStructuredMemory(_ProbeWriter, StructuredMemory):
    __slots__ = ()


WRITERS = {"prose": ProbeProseMemory, "json": ProbeStructuredMemory}


def writer_messages(fmt, previous_rendered, marker, observation, limit):
    return WRITERS[fmt]()._messages(previous_rendered, marker, observation,
                                    ProbeContext(PUBLIC_RULES, limit), limit)


# ---------------------------------------------------------------- planned reads

def qualification_reads(family: dict) -> list[dict]:
    """Q0 logical assessments at P12: six contexts per sibling world."""
    out = []
    f, roles = family["index"], family["roles"]
    for world in family["worlds"]:
        reduced = public_state(world["observations"])
        missing_by_omission = (f + world["world"]) % 2 == 0
        contexts = {
            "full_history": (history_context(world["observations"]), roles["target"], world["answer"]),
            "sufficient_prose": (prose_note(reduced), roles["target"], world["answer"]),
            "sufficient_json": (json_note(reduced), roles["target"], world["answer"]),
            "missing_prose": ((prose_note(reduced, roles["target"]), roles["target"], ABSTAIN)
                              if missing_by_omission else (prose_note(reduced), roles["revoked"], ABSTAIN)),
            "missing_json": ((json_note(reduced, roles["target"]), roles["target"], ABSTAIN)
                             if missing_by_omission else (json_note(reduced), roles["revoked"], ABSTAIN)),
            "no_memory": ("", roles["target"], world["answer"]),
        }
        for name in QUALIFICATION_CONTEXTS:
            memory, query, gold = contexts[name]
            out.append({"family_id": family["family_id"], "world": world["world"], "probe": "P12",
                        "condition": name, "memory": memory, "query": query, "gold": gold})
    return out


def reference_reads(family: dict, probe: str) -> list[dict]:
    out = []
    target = family["roles"]["target"]
    for world in family["worlds"]:
        seen = world["observations"][:PROBES[probe] + 1]
        reduced = public_state(seen)
        for name, memory in (("full_history", history_context(seen)), ("no_memory", ""),
                             ("sufficient_prose", prose_note(reduced)),
                             ("sufficient_json", json_note(reduced))):
            out.append({"family_id": family["family_id"], "world": world["world"], "probe": probe,
                        "condition": name, "memory": memory, "query": target, "gold": world["answer"]})
    return out


def distinct_prompts(reads: list[dict], options: list[str]) -> int:
    return len({digest([asdict(m) for m in reader_messages(r["memory"], r["query"], options)])
                for r in reads})


# ---------------------------------------------------------------- execution

class _CountLog:
    """Pass-through model that records every token count the writer requests."""

    def __init__(self, model):
        self._model = model
        self.counts = []

    @property
    def metadata(self):
        return self._model.metadata

    def count_tokens(self, text):
        count = self._model.count_tokens(text)
        self.counts.append({"text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                            "count": count})
        return count

    def generate(self, messages, *, purpose):
        return self._model.generate(messages, purpose=purpose)

    def score_choices(self, messages, *, labels):
        return self._model.score_choices(messages, labels=labels)


def _write_line(handle, record) -> None:
    handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
    handle.flush()


def _fsync_path(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class _Unit:
    """One durable unit (a family or Q0): events, writes and assessments plus a completion record."""

    def __init__(self, directory: Path, model, deadline, clock):
        directory.mkdir(parents=True, exist_ok=False)
        self.dir = directory
        self.files = {n: (directory / n).open("x", encoding="utf-8")
                      for n in ("events.jsonl", "writes.jsonl", "assessments.jsonl")}
        self.counter = _CountLog(model)
        self.context: dict = {"step": 0}
        self.request_id = -1
        self.sequence = 0
        self.deadline, self.clock = deadline, clock
        self.logged = _LoggedModel(self.counter, self._emit, lambda: self.context["step"])
        self.cache: dict = {}
        self.model_identity = digest(model.metadata)

    def _emit(self, event: str, **data) -> None:
        if event == "model_request":
            if self.clock() > self.deadline:
                raise StageTimeout("soft stage deadline reached before a model request")
            self.request_id += 1
        record = {"event": event, "sequence": self.sequence, "request_id": self.request_id,
                  **{k: v for k, v in self.context.items() if k != "step"}, **data}
        _write_line(self.files["events.jsonl"], record)
        self.sequence += 1

    def read(self, entry: dict, options: list[str], **identity) -> dict:
        """Score one logical assessment, reusing an exact-identity physical call if present."""
        messages = reader_messages(entry["memory"], entry["query"], options)
        prompt = digest([asdict(m) for m in messages])
        key = digest([prompt, list(LABELS), self.model_identity])  # gold never enters the key
        reused = key in self.cache
        if not reused:
            self.context = {"step": 0, "role": "reader", **identity}
            result = self.logged.score_choices(messages, labels=LABELS)
            self.cache[key] = {"request_id": self.request_id, "label": result.text}
        source = self.cache[key]
        chosen = options[LABELS.index(source["label"])]
        record = {**identity, "query": entry["query"], "gold": entry["gold"], "prompt_sha256": prompt,
                  "source_request_id": source["request_id"], "reused": reused,
                  "selected_label": source["label"], "chosen": chosen,
                  "correct": chosen == entry["gold"], "abstained": chosen == ABSTAIN}
        _write_line(self.files["assessments.jsonl"], record)
        return record

    def chain(self, family: dict, world: dict, fmt: str, limit: int) -> dict:
        """Fourteen writes; returns rendered snapshots at P0 and P12."""
        writer = WRITERS[fmt]()
        state = writer.empty()
        snapshots = {}
        for i, observation in enumerate(world["observations"]):
            identity = {"family_id": family["family_id"], "world": world["world"], "format": fmt,
                        "allowance": limit, "write_index": i}
            self.context = {"step": i, "role": "writer", **identity}
            self.counter.counts = []
            first = self.request_id + 1
            result = writer.update(state, INITIAL if i == 0 else UPDATE, observation,
                                   ProbeContext(PUBLIC_RULES, limit), self.logged)
            _write_line(self.files["writes.jsonl"], {
                **identity, "previous_state": state, "state": result.memory,
                "rendered": writer.render(result.memory), "update_events": list(result.events),
                "request_ids": list(range(first, self.request_id + 1)),
                "token_counts": self.counter.counts})
            state = result.memory
            for probe, index in PROBES.items():
                if i == index:
                    snapshots[probe] = writer.render(state)
        return snapshots

    def complete(self, summary: dict, commit) -> dict:
        for handle in self.files.values():
            handle.flush()
            os.fsync(handle.fileno())
            handle.close()
        (self.dir / "summary.json").open("x").write(json.dumps(summary, indent=1, sort_keys=True))
        _fsync_path(self.dir / "summary.json")
        names = sorted([*self.files, "summary.json"])
        record = {"files": {n: file_sha256(self.dir / n) for n in names}, "complete": True}
        with (self.dir / "completion.json").open("x") as handle:
            handle.write(json.dumps(record, indent=1, sort_keys=True))
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_path(self.dir)
        commit()  # Durable before any later unit starts.
        return record

    def close(self) -> None:
        for handle in self.files.values():
            if not handle.closed:
                handle.flush()
                handle.close()


def run_family(family: dict, allowances: tuple[int, int], directory: Path, model, *,
               commit, deadline=float("inf"), clock=time.monotonic) -> dict:
    """Full grid for one family: 16 chains, primary reads, references, carry-forward."""
    started = clock()
    unit = _Unit(directory, model, deadline, clock)
    try:
        options = family["options"]
        target = family["roles"]["target"]
        for world in family["worlds"]:
            for fmt in FORMATS:
                for limit in allowances:
                    snaps = unit.chain(family, world, fmt, limit)
                    base = {"family_id": family["family_id"], "world": world["world"], "format": fmt,
                            "allowance": limit}
                    p0 = None
                    for probe, memory in snaps.items():
                        rec = unit.read({"memory": memory, "query": target, "gold": world["answer"]},
                                        options, kind="primary", probe=probe, **base)
                        p0 = rec if probe == "P0" else p0
                    _write_line(unit.files["assessments.jsonl"], {
                        **base, "kind": "carry_forward", "probe": "P12", "query": target,
                        "gold": world["answer"], "prompt_sha256": p0["prompt_sha256"],
                        "source_request_id": p0["source_request_id"], "reused": True,
                        "selected_label": p0["selected_label"], "chosen": p0["chosen"],
                        "correct": p0["correct"], "abstained": p0["abstained"]})
        for probe in PROBES:
            for entry in reference_reads(family, probe):
                unit.read(entry, options, kind="reference", probe=probe, family_id=entry["family_id"],
                          world=entry["world"], condition=entry["condition"])
        summary = {"family_id": family["family_id"], "allowances": list(allowances),
                   "wall_seconds": clock() - started, "physical_requests": unit.request_id + 1}
        return unit.complete(summary, commit)
    finally:
        unit.close()


def run_qualification(families: list[dict], directory: Path, model, *, commit,
                      deadline=float("inf"), clock=time.monotonic) -> dict:
    started = clock()
    unit = _Unit(directory, model, deadline, clock)
    try:
        for family in families:
            unit.cache = {}  # reuse is within a family only
            for entry in qualification_reads(family):
                unit.read(entry, family["options"], kind="qualification", probe="P12",
                          family_id=entry["family_id"], world=entry["world"],
                          condition=entry["condition"])
        return unit.complete({"wall_seconds": clock() - started,
                              "physical_requests": unit.request_id + 1}, commit)
    finally:
        unit.close()


def _status(directory: Path, name: str, record: dict, commit) -> None:
    with (directory / name).open("x") as handle:
        handle.write(json.dumps(record, indent=1, sort_keys=True))
        handle.flush()
        os.fsync(handle.fileno())
    commit()


def run_stage(stage: str, package: Path, output: Path, model, *, commit, low: int | None = None,
              families: list[str] | None = None, deadline=float("inf"), clock=time.monotonic) -> dict:
    """S1 (Q0, then pilot only if Q0 passes) or S2 (listed test families). Real models are
    supplied by the authorized worker; evidence stays fake-labeled when the model is."""
    splits = load_splits(package)
    output.mkdir(parents=True, exist_ok=False)
    real = model.metadata.get("is_fake") is False
    status = {"stage": stage, "model_is_fake": not real}
    try:
        if stage == "s1":
            run_qualification(splits["qualification"], output / "qualification", model,
                              commit=commit, deadline=deadline, clock=clock)
            gate = qualification_gate(output / "qualification", splits["qualification"], real=real)
            status["qualification"] = gate
            if not gate["passed"]:
                status["outcome"] = "valid_research_stop"
                _status(output, "stage-status.json", status, commit)
                return status
            for family in splits["dev"]:
                run_family(family, (PILOT_LOW, HIGH), output / family["family_id"], model,
                           commit=commit, deadline=deadline, clock=clock)
            status["pilot"] = pilot_decision([output / f["family_id"] for f in splits["dev"]],
                                             splits["dev"], real=real)
            if status["pilot"]["complete"] is not True:
                # No budget decision from an incomplete or unauditable pilot.
                raise AuditError(f"pilot incomplete: {status['pilot'].get('reason')}")
            status["outcome"] = ("valid_research_stop" if status["pilot"]["stop"] is True
                                 else "pilot_complete")
        elif stage == "s2":
            if low not in {PILOT_LOW, FLOOR_LOW}:
                raise ValueError("S2 requires the S1-selected B_low (64 or 128)")
            by_id = {f["family_id"]: f for f in splits["test"]}
            for fid in families or list(by_id):
                run_family(by_id[fid], (low, HIGH), output / fid, model, commit=commit,
                           deadline=deadline, clock=clock)
            status["outcome"] = "families_complete"
        else:
            raise ValueError("stage must be s1 or s2")
        _status(output, "stage-status.json", status, commit)
        return status
    except BaseException as error:
        status.update(outcome="timeout" if isinstance(error, StageTimeout) else "error",
                      error_type=type(error).__name__, error=str(error),
                      traceback=traceback.format_exc())
        _status(output, "stage-status.json", status, commit)
        raise


# ---------------------------------------------------------------- audit

def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def verify_completion(directory: Path) -> dict:
    record_path = directory / "completion.json"
    if not record_path.exists():
        raise AuditError(f"{directory.name}: no completion record")
    record = json.loads(record_path.read_text())
    for name, expected in record["files"].items():
        path = directory / name
        if not path.exists():
            raise AuditError(f"{directory.name}: missing {name}")
        if file_sha256(path) != expected:
            raise AuditError(f"{directory.name}: hash mismatch for {name}")
    return record


def _candidate(fmt: str, text: str) -> tuple[str | None, str | None]:
    """Independent acceptance routing under the declared p1 syntax/rendering policy.

    Returns (rendered, None) for a syntactically valid candidate, else (None, reason)."""
    try:
        if fmt == "prose":
            _text(text)
            return text, None
        return _serialize(_object(text)), None
    except _InvalidMemory as error:
        return None, str(error)


# p1-memory-v17 repair turn; tests pin it to the pre-refactor capture.
REPAIR_INSTRUCTION = ("Candidate rejected: {reason}. Rewrite using the same supplied evidence and "
                      "required format. The complete rendering must fit {limit} tokens. Return only "
                      "the replacement memory.")


def _restricted_argmax(logits: list[float]) -> int:
    return logits.index(max(logits))


def audit_unit(directory: Path, families: list[dict], *, real: bool) -> dict:
    """Recompute writer routing and reader decisions from raw evidence; never calls a model."""
    verify_completion(directory)
    events = _jsonl(directory / "events.jsonl")
    by_family = {f["family_id"]: f for f in families}
    requests, responses = {}, {}
    for e in events:
        if e["event"] == "model_error":
            raise AuditError(f"{directory.name}: model error in a completed unit")
        if e["event"] == "model_request":
            requests[e["request_id"]] = e
        elif e["event"] == "model_response":
            responses[e["request_id"]] = e
    if set(requests) != set(responses) or sorted(requests) != list(range(len(requests))):
        raise AuditError(f"{directory.name}: requests and responses do not pair")
    writes = _jsonl(directory / "writes.jsonl")
    previous = {}
    for w in writes:
        family = by_family[w["family_id"]]
        world = family["worlds"][w["world"]]
        chain = (w["family_id"], w["world"], w["format"], w["allowance"])
        expected_previous = previous.get(chain, "" if w["format"] == "prose" else "{}")
        if w["write_index"] != (0 if chain not in previous else previous[chain + ("i",)] + 1):
            raise AuditError("writer chain out of order")
        if w["previous_state"] != expected_previous:
            raise AuditError("writer previous state does not match the stored chain state")
        counts = {c["text_sha256"]: c["count"] for c in w["token_counts"]}
        ids = w["request_ids"]
        if not 1 <= len(ids) <= 2:
            raise AuditError("writer made an unexpected number of calls")
        first = requests[ids[0]]
        payload = json.loads(first["messages"][1]["content"])
        marker = INITIAL if w["write_index"] == 0 else UPDATE
        if set(payload) != WRITER_FIELDS:
            raise AuditError("writer payload fields differ from the whitelist")
        if first["messages"] != [asdict(m) for m in writer_messages(
                w["format"], _render(w["format"], expected_previous), marker,
                world["observations"][w["write_index"]], w["allowance"])]:
            raise AuditError("writer request differs from the frozen protocol")
        stored, expected_events = None, []
        for attempt, rid in enumerate(ids):
            purpose = "memory" if attempt == 0 else "memory_repair"
            if requests[rid]["purpose"] != purpose:
                raise AuditError("writer call purpose out of order")
            text = responses[rid]["text"]
            rendered, reason = _candidate(w["format"], text)
            if rendered is not None:
                count = counts.get(hashlib.sha256(rendered.encode("utf-8")).hexdigest())
                if count is None:
                    raise AuditError("accepted-candidate token count missing")
                if count > w["allowance"]:
                    rendered, reason = None, f"over_budget:{count}>{w['allowance']}"
            if rendered is not None:
                if attempt + 1 != len(ids):
                    raise AuditError("a repair followed an acceptable candidate")
                if rendered != text:
                    expected_events.append(f"{purpose}_json_canonicalized")
                expected_events.append(f"{purpose}_accepted")
                stored = rendered
                break
            expected_events.append(f"{purpose}_rejected:{reason}")
            if attempt == 0:
                repair = requests.get(ids[1]) if len(ids) == 2 else None
                if repair is None:
                    raise AuditError("rejected candidate without a repair call")
                expected_repair = [*first["messages"], {"role": "assistant", "content": text},
                                   {"role": "user", "content": REPAIR_INSTRUCTION.format(
                                       reason=reason, limit=w["allowance"])}]
                if repair["messages"] != expected_repair:
                    raise AuditError("repair request differs from the v17 repair policy")
        if stored is None:
            stored = expected_previous  # exact previous-valid-state fallback
            expected_events.append("memory_fallback:previous_valid_memory")
        if w["update_events"] != expected_events:
            raise AuditError("recorded writer events differ from the reconstructed routing")
        if w["state"] != stored or w["rendered"] != _render(w["format"], stored):
            raise AuditError("stored memory differs from the routed writer output")
        previous[chain] = stored
        previous[chain + ("i",)] = w["write_index"]
    snapshots = {}
    for w in writes:
        for probe, index in PROBES.items():
            if w["write_index"] == index:
                snapshots[(w["family_id"], w["world"], w["format"], w["allowance"], probe)] = w["rendered"]
    for chain in [k for k in previous if len(k) == 4]:
        if previous[chain + ("i",)] != 13:
            raise AuditError("writer chain incomplete")
    assessments = _jsonl(directory / "assessments.jsonl")
    for a in assessments:
        family = by_family[a["family_id"]]
        request = requests.get(a["source_request_id"])
        response = responses.get(a["source_request_id"])
        if request is None or response is None or request["purpose"] != "action":
            raise AuditError("assessment does not reference a reader request")
        if digest(request["messages"]) != a["prompt_sha256"]:
            raise AuditError("assessment prompt differs from its source request")
        meta = response["metadata"]
        if real and (meta.get("scoring_evidence") != "actual_model_forward"):
            raise AuditError("real stage evidence is not an actual model forward")
        if meta.get("labels") != list(LABELS):
            raise AuditError("reader labels differ from the protocol")
        label = LABELS[_restricted_argmax(meta["candidate_logits"])]
        if label != response["text"] or label != meta.get("selected_label") or label != a["selected_label"]:
            raise AuditError("selected label does not follow the recorded logits")
        chosen = family["options"][LABELS.index(label)]
        if chosen != a["chosen"] or (chosen == a["gold"]) != a["correct"]:
            raise AuditError("chosen option or correctness does not reconcile")
        world = family["worlds"][a["world"]]
        if a["kind"] in {"primary", "carry_forward"}:
            if a["query"] != family["roles"]["target"] or a["gold"] != world["answer"]:
                raise AuditError("primary query or gold differs from the frozen family")
            probe = "P0" if a["kind"] == "carry_forward" else a["probe"]
            memory = snapshots[(a["family_id"], a["world"], a["format"], a["allowance"], probe)]
            expected = digest([asdict(m) for m in reader_messages(memory, a["query"], family["options"])])
            if expected != a["prompt_sha256"]:
                raise AuditError("reader memory block differs from the stored snapshot")
        else:
            planned = (qualification_reads(family) if a["kind"] == "qualification"
                       else reference_reads(family, a["probe"]))
            entry = next((r for r in planned if r["world"] == a["world"]
                          and r["condition"] == a["condition"]), None)
            if entry is None or (entry["query"], entry["gold"]) != (a["query"], a["gold"]) or digest(
                    [asdict(m) for m in reader_messages(entry["memory"], entry["query"],
                                                        family["options"])]) != a["prompt_sha256"]:
                raise AuditError("control prompt or gold differs from the frozen public evidence")
    if real:
        for r in responses.values():
            meta = r["metadata"]
            if r["purpose"] != "action" and (meta.get("do_sample") is not False
                                             or meta.get("use_model_defaults") is not False):
                raise AuditError("real writer evidence lacks greedy-decoding metadata")
    reader_calls = sum(1 for r in requests.values() if r["purpose"] == "action")
    return {"unit": directory.name, "requests": len(requests), "reader_calls": reader_calls,
            "writes": len(writes), "assessments": len(assessments)}


def _render(fmt: str, state: str) -> str:
    return state if fmt == "prose" else _serialize(_object(state))


def _assessment_key(a: dict) -> tuple:
    return (a["family_id"], a["kind"], a["world"], a.get("format"), a.get("allowance"),
            a.get("condition"), a["probe"])


def _require_exact(actual: list[tuple], expected: list[tuple], what: str) -> None:
    """Every planned identity exactly once: no duplicates, missing or unexpected cells."""
    if len(set(actual)) != len(actual):
        raise AuditError(f"{what}: duplicated identity")
    if set(actual) != set(expected):
        raise AuditError(f"{what}: missing or unexpected identities")


def expected_family_keys(family: dict, allowances: tuple[int, int]) -> list[tuple]:
    fid, worlds = family["family_id"], range(4)
    keys = [(fid, "primary", w, fmt, b, None, p) for w in worlds for fmt in FORMATS
            for b in allowances for p in PROBES]
    keys += [(fid, "carry_forward", w, fmt, b, None, "P12") for w in worlds for fmt in FORMATS
             for b in allowances]
    keys += [(fid, "reference", w, None, None, c, p) for w in worlds for c in PRIMARY_CONTEXTS
             for p in PROBES]
    return keys


def audit_family(directory: Path, family: dict, *, real: bool, allowances: tuple[int, int]) -> dict:
    result = audit_unit(directory, [family], real=real)
    assessments = _jsonl(directory / "assessments.jsonl")
    _require_exact([_assessment_key(a) for a in assessments], expected_family_keys(family, allowances),
                   f"{family['family_id']} assessment coverage")
    writes = _jsonl(directory / "writes.jsonl")
    _require_exact([(w["world"], w["format"], w["allowance"], w["write_index"]) for w in writes],
                   [(w, fmt, b, i) for w in range(4) for fmt in FORMATS for b in allowances
                    for i in range(14)], f"{family['family_id']} write coverage")
    kinds = {k: sum(a["kind"] == k for a in assessments) for k in ("primary", "reference", "carry_forward")}
    if result["reader_calls"] > 49:
        raise AuditError(f"{family['family_id']}: more physical reader calls than planned")
    if json.loads((directory / "summary.json").read_text())["allowances"] != list(allowances):
        raise AuditError("family allowances differ from the stage decision")
    return {**result, **kinds}


# ---------------------------------------------------------------- gates and analysis

def qualification_gate(directory: Path, families: list[dict], *, real: bool = False) -> dict:
    audit = audit_unit(directory, families, real=real)
    rows = _jsonl(directory / "assessments.jsonl")
    _require_exact([_assessment_key(r) for r in rows],
                   [(f["family_id"], "qualification", w, None, None, c, "P12")
                    for f in families for w in range(4) for c in QUALIFICATION_CONTEXTS],
                   "qualification assessment coverage")
    tally = {c: sum(r["correct"] for r in rows if r["condition"] == c) for c in QUALIFICATION_CONTEXTS}
    events = _jsonl(directory / "events.jsonl")
    identical = True
    for family in families:
        sent = {}
        for e in events:
            if e["event"] == "model_request" and e["family_id"] == family["family_id"]:
                query = e["messages"][1]["content"].rsplit("What is ", 1)[1].split("'s current", 1)[0]
                sent.setdefault((e["condition"], query), set()).add(outside_memory(e["messages"]))
        identical &= all(len(v) == 1 for v in sent.values())
    checks = {
        "full_history": tally["full_history"] >= 15,
        "sufficient_prose": tally["sufficient_prose"] >= 15,
        "sufficient_json": tally["sufficient_json"] >= 15,
        "missing_prose": tally["missing_prose"] >= 15,
        "missing_json": tally["missing_json"] >= 15,
        "no_memory_at_most_4": tally["no_memory"] <= 4,
        "sibling_inputs_identical": identical,
        "zero_technical_failures": True,  # audit_unit rejects any model_error
    }
    return {"passed": all(checks.values()), "checks": checks, "correct": tally,
            "distinct_prompts": audit["reader_calls"], "logical_assessments": len(rows)}


def pilot_decision(directories: list[Path], families: list[dict], *, real: bool = False) -> dict:
    rows = []
    for directory, family in zip(directories, families):
        try:
            audit_family(directory, family, real=real, allowances=(PILOT_LOW, HIGH))
        except (AuditError, FileNotFoundError) as error:
            return {"complete": False, "stop": None, "low": None, "reason": str(error)}
        rows += [a for a in _jsonl(directory / "assessments.jsonl")
                 if a["kind"] == "primary" and a["probe"] == "P12"]
    return {"complete": True, **pilot_rule(rows)}


def pilot_rule(rows: list[dict]) -> dict:
    """Stop if both formats have at most 2/8 at P12/256; else 128 if pooled P12/64 < 4/16."""
    if len(rows) != 32:
        raise AuditError("pilot rule requires 32 P12 primary decisions")
    high = {fmt: sum(a["correct"] for a in rows if a["format"] == fmt and a["allowance"] == HIGH)
            for fmt in FORMATS}
    low_pooled = sum(a["correct"] for a in rows if a["allowance"] == PILOT_LOW)
    stop = all(v <= 2 for v in high.values())
    return {"stop": stop, "p12_high_correct": high, "p12_low64_pooled": low_pooled,
            "low": None if stop else (FLOOR_LOW if low_pooled < 4 else PILOT_LOW)}


def family_interaction(rows: list[dict], low: int) -> float:
    """D_f at P12 from one family's primary decisions (sibling means per cell)."""
    def a(fmt, b):
        sel = [r for r in rows if r["kind"] == "primary" and r["probe"] == "P12"
               and r["format"] == fmt and r["allowance"] == b]
        if len(sel) != 4:
            raise AuditError("each P12 cell needs four sibling decisions")
        return sum(r["correct"] for r in sel) / 4
    return (a("json", low) - a("prose", low)) - (a("json", HIGH) - a("prose", HIGH))


def _accuracy(rows):
    return sum(r["correct"] for r in rows) / len(rows) if rows else None


def bootstrap(updated: list[float], untouched: list[float], *, samples=10000, seed=0) -> dict:
    rng = random.Random(seed)
    stats = sorted((sum(rng.choices(updated, k=len(updated))) / len(updated)
                    + sum(rng.choices(untouched, k=len(untouched))) / len(untouched)) / 2
                   for _ in range(samples))
    return {"samples": samples, "seed": seed, "lower_2_5": stats[249], "upper_97_5": stats[9749],
            "note": "four families per stratum; small-sample description, coverage not established"}


def analyze(directories: dict[str, Path], test: list[dict], low: int, *, real: bool) -> dict:
    """Complete-coverage analysis from audited raw decisions; refuses partial studies."""
    if sorted(directories) != sorted(f["family_id"] for f in test):
        raise AuditError("analysis requires all eight test families")
    rows, writes, audits = [], [], {}
    for family in test:
        d = directories[family["family_id"]]
        audits[family["family_id"]] = audit_family(d, family, real=real, allowances=(low, HIGH))
        rows += [{**a, "query_type": family["query_type"]} for a in _jsonl(d / "assessments.jsonl")]
        writes += _jsonl(d / "writes.jsonl")
    cells = {}
    for fmt in FORMATS:
        for b in (low, HIGH):
            for probe in PROBES:
                sel = [r for r in rows if r["kind"] == "primary" and r["format"] == fmt
                       and r["allowance"] == b and r["probe"] == probe]
                cells[f"{fmt}|{b}|{probe}"] = {
                    "accuracy": _accuracy(sel), "abstention": sum(r["abstained"] for r in sel) / len(sel),
                    "destination_coverage": sum(not r["abstained"] for r in sel) / len(sel), "n": len(sel)}
            cf = [r for r in rows if r["kind"] == "carry_forward" and r["format"] == fmt and r["allowance"] == b]
            cells[f"{fmt}|{b}|carry_forward"] = {"accuracy": _accuracy(cf), "n": len(cf)}
    controls = {f"{c}|{p}": _accuracy([r for r in rows if r["kind"] == "reference"
                                       and r["condition"] == c and r["probe"] == p])
                for c in PRIMARY_CONTEXTS for p in PROBES}
    d_f = {f["family_id"]: family_interaction([r for r in rows if r["family_id"] == f["family_id"]], low)
           for f in test}
    upd = [d_f[f["family_id"]] for f in test if f["query_type"] == "updated"]
    unt = [d_f[f["family_id"]] for f in test if f["query_type"] == "untouched"]
    costs = {}
    for fmt in FORMATS:
        for b in (low, HIGH):
            sel = [w for w in writes if w["format"] == fmt and w["allowance"] == b]
            costs[f"{fmt}|{b}"] = {
                "writes": len(sel),
                "repairs": sum(len(w["request_ids"]) == 2 for w in sel),
                "fallbacks": sum("memory_fallback:previous_valid_memory" in w["update_events"] for w in sel)}
    return {"protocol": PROTOCOL, "question": f"256 versus {low} tokens", "low": low, "cells": cells,
            "controls": controls, "d_f": d_f,
            "primary_estimate": (sum(upd) / len(upd) + sum(unt) / len(unt)) / 2,
            "signs": {"positive": sum(v > 0 for v in d_f.values()), "negative": sum(v < 0 for v in d_f.values()),
                      "zero": sum(v == 0 for v in d_f.values())},
            "bootstrap": bootstrap(upd, unt), "writer_costs": costs, "audits": audits,
            "limits": "eight independent families; whole-system comparison; no claims about internal "
                      "reasoning, general reliability, CookingWorld transfer or capacity"}


def annotation_plan(test: list[dict]) -> list[dict]:
    """Balanced P12 snapshot selection, from a dedicated stream independent of outcomes."""
    plan = []
    for kind in ("updated", "untouched"):
        families = [f for f in test if f["query_type"] == kind]
        destinations = list(DESTINATIONS)
        stream("test", "annotation", kind).shuffle(destinations)
        for family, destination in zip(families, destinations):
            plan.append({"family_id": family["family_id"], "query_type": kind,
                         "world": DESTINATIONS.index(destination), "answer": destination})
    return plan


def annotation_sheet(plan: list[dict], directories: dict[str, Path], test: list[dict], low: int) -> list[dict]:
    by_id = {f["family_id"]: f for f in test}
    rows = []
    for item in plan:
        family = by_id[item["family_id"]]
        world = family["worlds"][item["world"]]
        for w in _jsonl(directories[item["family_id"]] / "writes.jsonl"):
            if w["world"] == item["world"] and w["write_index"] == 13:
                rows.append({"family_id": item["family_id"], "world": item["world"], "format": w["format"],
                             "allowance": w["allowance"], "queried_entity": family["roles"]["target"],
                             "public_observations": world["observations"][:2], "snapshot": w["rendered"],
                             "category": None, "revoked_claimed_known": None, "notes": None})
    if len(rows) != 32:
        raise AuditError("annotation sheet requires 32 snapshots")
    return rows


# ---------------------------------------------------------------- preflight and package

def actual_preflight(package: Path, tokenizer, *, vocab_size: int, context_limit=8192,
                     writer_cap=1024, evidence="scripted_tokenizer_fixture") -> dict:
    """Run inside the authorized worker with the cached pinned tokenizer, before weights load."""
    from .transformers_model import validate_choice_tokens

    splits = load_splits(package)

    def render(messages):
        return tokenizer.apply_chat_template([asdict(m) for m in messages], tokenize=False,
                                             add_generation_prompt=True)

    report = {"evidence": evidence, "reader_prompts": 0, "notes": {}, "passed": True}
    seen = set()
    for family in splits["qualification"]:
        for entry in qualification_reads(family):
            prompt = render(reader_messages(entry["memory"], entry["query"], family["options"]))
            if prompt in seen:
                continue
            seen.add(prompt)
            ids = validate_choice_tokens(tokenizer, prompt, LABELS, vocab_size)
            if len(tokenizer.encode(prompt, add_special_tokens=False)) + 1 > context_limit:
                raise ValueError("qualification prompt exceeds the context limit")
            report["label_token_ids"] = list(ids)
    report["reader_prompts"] = len(seen)
    for families in splits.values():
        for family in families:
            for world in family["worlds"]:
                reduced = public_state(world["observations"])
                for name, note in (("prose", prose_note(reduced)), ("json", json_note(reduced))):
                    count = len(tokenizer.encode(note, add_special_tokens=False))
                    report["notes"][f"{family['family_id']}/{world['world']}/{name}"] = count
                    if count > HIGH:
                        report["passed"] = False
                for fmt in FORMATS:
                    prompt = render(writer_messages(fmt, WRITERS[fmt]().empty(), INITIAL,
                                                    world["observations"][0], HIGH))
                    if len(tokenizer.encode(prompt, add_special_tokens=False)) + writer_cap > context_limit:
                        raise ValueError("first writer prompt exceeds the context limit")
    template = tokenizer.chat_template if isinstance(getattr(tokenizer, "chat_template", None), str) else ""
    report["template_sha256"] = hashlib.sha256(template.encode("utf-8")).hexdigest()
    report["package_manifest_sha256"] = json.loads((package / "manifest.json").read_text())["manifest_sha256"]
    return report


SOURCE_FILES = ("game_memory/memory_probe.py", "game_memory/memory.py", "game_memory/runner.py",
                "game_memory/components.py", "game_memory/transformers_model.py",
                "game_memory/contracts.py", "game_memory/environment.py", "game_memory/__init__.py",
                "tests/test_memory_probe.py", "tests/fixtures/v17-writer-messages.json",
                "docs/memory-probe-v1.md", "AGENTS.md", "pytest.ini")


def load_splits(package: Path) -> dict:
    manifest = json.loads((package / "manifest.json").read_text())
    splits = {}
    for split, info in manifest["splits"].items():
        path = package / info["path"]
        if file_sha256(path) != info["sha256"]:
            raise AuditError(f"split file {split} differs from the manifest")
        splits[split] = json.loads(path.read_text())
    return splits


def verify_source(package: Path, root: Path) -> dict:
    manifest = json.loads((package / "manifest.json").read_text())
    mismatched = [p for p, h in manifest["source_files"].items()
                  if not (root / p).exists() or file_sha256(root / p) != h]
    return {"matches": not mismatched, "mismatched": mismatched}


def prepare(output: Path, root: Path, *, parent_commit: str) -> dict:
    splits = generate_splits()
    output.mkdir(parents=True, exist_ok=False)
    (output / "splits").mkdir()
    split_info = {}
    for split, families in splits.items():
        path = output / "splits" / f"{split}.json"
        path.open("x").write(json.dumps(families, indent=1, sort_keys=True, ensure_ascii=False))
        split_info[split] = {"path": f"splits/{split}.json", "sha256": file_sha256(path),
                             "family_ids": [f["family_id"] for f in families]}
    q_distinct = sum(distinct_prompts(qualification_reads(f), f["options"]) for f in splits["qualification"])
    ref_physical = [distinct_prompts(reference_reads(f, "P0") + reference_reads(f, "P12"), f["options"])
                    for f in splits["test"]]
    plan = annotation_plan(splits["test"])
    (output / "annotation-plan.json").open("x").write(json.dumps(plan, indent=1, sort_keys=True))
    with zipfile.ZipFile(output / "source.zip", "x") as archive:
        for rel in SOURCE_FILES:
            archive.write(root / rel, rel)
    manifest = {
        "protocol": PROTOCOL, "writer_version": WRITER_VERSION, "reader_version": READER_VERSION,
        "model": {"id": MODEL_ID, "revision": MODEL_REVISION, "dtype": "float16", "device": "cuda",
                  "do_sample": False, "num_beams": 1, "use_model_defaults": False,
                  "generation_seed": 0, "context_limit": 8192, "memory_max_new_tokens": 1024,
                  "reader": "legal_label_argmax_v1 over A-E, first-listed tie"},
        "texts": {"public_rules": PUBLIC_RULES, "reader_instruction": READER_INSTRUCTION,
                  "writer_instruction": WRITER_INSTRUCTION,
                  "format_instructions": {"prose": ProseMemory.format_instructions,
                                          "json": StructuredMemory.format_instructions}},
        "text_sha256": {k: hashlib.sha256(v.encode()).hexdigest() for k, v in
                        (("public_rules", PUBLIC_RULES), ("reader_instruction", READER_INSTRUCTION),
                         ("writer_instruction", WRITER_INSTRUCTION))},
        "seeds": "random.Random(int.from_bytes(sha256('memory-probe-v1|0|<purpose>')[:8], 'big'))",
        "splits": split_info, "allowances": {"high": HIGH, "pilot_low": PILOT_LOW, "floor_low": FLOOR_LOW},
        "planned": {"qualification_logical": 96, "qualification_distinct_prompts": q_distinct,
                    "per_family": {"writes": 224, "primary_logical": 32, "reference_logical": 32,
                                   "carry_forward_logical": 16, "max_physical_reader": 49,
                                   "reference_physical_by_test_family": ref_physical},
                    "ceilings": {"s1_requests": 1070, "s2_requests": 3976, "study_requests": 5046}},
        "annotation_plan_sha256": file_sha256(output / "annotation-plan.json"),
        "source_files": {rel: file_sha256(root / rel) for rel in SOURCE_FILES},
        "source_zip_sha256": file_sha256(output / "source.zip"),
        "parent_commit": parent_commit, "worktree_dirty": True,
    }
    manifest["manifest_sha256"] = digest(manifest)
    (output / "manifest.json").open("x").write(json.dumps(manifest, indent=1, sort_keys=True,
                                                          ensure_ascii=False))
    files = {p.name: file_sha256(p) for p in sorted(output.iterdir()) if p.is_file()}
    files.update({f"splits/{p.name}": file_sha256(p) for p in sorted((output / "splits").iterdir())})
    (output / "package-files-sha256.json").open("x").write(json.dumps(files, indent=1, sort_keys=True))
    return manifest


def fixture_preflight(package: Path) -> dict:
    """Synthetic checks only: character counts are not tokenizer evidence."""
    splits = load_splits(package)
    manifest = json.loads((package / "manifest.json").read_text())
    q = sum(distinct_prompts(qualification_reads(f), f["options"]) for f in splits["qualification"])
    notes = {f"{f['family_id']}/{w['world']}/{name}": len(note)
             for fs in splits.values() for f in fs for w in f["worlds"]
             for name, note in (("prose", prose_note(public_state(w["observations"]))),
                                ("json", json_note(public_state(w["observations"]))))}
    return {"evidence": "synthetic_fixture_not_tokenizer_evidence",
            "package_manifest_sha256": manifest["manifest_sha256"],
            "qualification_distinct_prompts": q, "note_character_counts": notes,
            "actual_tokenizer_preflight": "unexecuted: runs inside the authorized S1 worker"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--parent-commit", required=True)
    f = sub.add_parser("fixture-preflight")
    f.add_argument("--package", type=Path, required=True)
    f.add_argument("--output", type=Path, required=True)
    v = sub.add_parser("verify-source")
    v.add_argument("--package", type=Path, required=True)
    a = sub.add_parser("analyze")
    a.add_argument("--package", type=Path, required=True)
    a.add_argument("--stage-dir", type=Path, action="append", required=True)
    a.add_argument("--low", type=int, required=True)
    a.add_argument("--output", type=Path, required=True)
    s = sub.add_parser("annotation-sheet")
    s.add_argument("--package", type=Path, required=True)
    s.add_argument("--stage-dir", type=Path, action="append", required=True)
    s.add_argument("--low", type=int, required=True)
    s.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.command == "prepare":
        print(json.dumps({"manifest_sha256": prepare(args.output, root,
                                                     parent_commit=args.parent_commit)["manifest_sha256"]}))
    elif args.command == "fixture-preflight":
        args.output.open("x").write(json.dumps(fixture_preflight(args.package), indent=1, sort_keys=True))
    elif args.command == "verify-source":
        result = verify_source(args.package, root)
        print(json.dumps(result))
        raise SystemExit(0 if result["matches"] else 1)
    else:
        test = load_splits(args.package)["test"]
        dirs = {d.name: d for stage in args.stage_dir for d in stage.iterdir()
                if d.is_dir() and d.name.startswith("T")}
        result = (analyze(dirs, test, args.low, real=True) if args.command == "analyze" else
                  annotation_sheet(json.loads((args.package / "annotation-plan.json").read_text()),
                                   dirs, test, args.low))
        args.output.open("x").write(json.dumps(result, indent=1, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
