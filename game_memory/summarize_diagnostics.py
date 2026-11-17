"""Audit real pilot logs and traces; never interpret fixtures as model capability."""

import argparse
from hashlib import sha256
from collections import Counter
import json
import math
import re
from pathlib import Path

from .actor import validate_action_output
from .components import FINALIZATION_REPAIR_POLICY


def analyze_events(events: list[dict]) -> dict:
    """Classify output errors against the public view at each generation.

    A score plateau is a diagnostic proxy, not a reason to terminate or replace
    actions. Inventory actions below are observations of commands, not an
    inferred oracle inventory. The actor receives none of these derived fields.
    """
    header = next((e for e in events if e["event"] == "episode_start"), {})
    choice_policy = header.get("components", {}).get("actor", {}).get("implementation") == "LegalChoiceActor"
    current_view = None
    responses = {}
    validations = {"action": Counter(), "action_review": Counter(),
                   "action_repair": Counter()}
    turns = []
    inventory_actions = []
    frequencies = Counter()
    recipe_observations = set()
    recipe_count = recipe_cost = movement_attempts = 0
    best_score = 0.0
    observed_score = False
    no_increase = longest_no_increase = 0
    last_increase = None
    streak_action = None
    streak_start = streak_attempts = streak_executions = 0
    longest_streak = {"action": None, "attempts": 0, "executions": 0,
                      "first_step": None, "last_step": None}
    for event in events:
        name = event["event"]
        if name == "reset":
            current_view = event["view"]
        elif name == "model_response" and event["purpose"] in validations:
            purpose = event["purpose"]
            text = event.get("text")
            allowed = current_view.get("allowed_actions") if current_view is not None else None
            if text is None:
                reason = "response_text_missing"
            elif choice_policy:
                reason = None if text == event.get("metadata", {}).get("selected_label") else "invalid_choice"
            else:
                _, reason = validate_action_output(text, allowed)
            classification = reason or ("choice" if choice_policy else "valid")
            validations[purpose][classification] += 1
            responses[(event["step"], purpose)] = (text, classification)
        elif name == "action":
            step, transition = event["step"], event["transition"]
            action = transition.get("action", "")
            view = transition.get("view", {})
            first, first_reason = responses.get((step, "action"), (None, "response_missing"))
            review, review_reason = responses.get((step, "action_review"), (None, None))
            repair, repair_reason = responses.get((step, "action_repair"), (None, None))
            row = {
                "step": step, "action": action,
                "first_response": first, "first_response_validation": first_reason,
                "review_response": review, "review_response_validation": review_reason,
                "repair_response": repair, "repair_response_validation": repair_reason,
                "valid_action": transition.get("valid_action"),
                "executed": transition.get("executed"),
                "action_cost": transition.get("action_cost"),
                "budget_remaining": view.get("budget_remaining"),
                "score": transition.get("score"), "observation": view.get("observation"),
            }
            turns.append(row)
            frequencies[action] += 1
            movement_attempts += action.startswith("move ")
            if transition.get("recipe_recheck"):
                recipe_count += 1
                recipe_cost += transition["action_cost"]
                recipe_observations.add(view.get("observation"))
            if transition.get("executed") and (action == "inventory" or
                                                action.startswith(("take ", "put "))):
                inventory_actions.append({"step": step, "action": action,
                                          "observation": view.get("observation")})
            score = transition.get("score")
            if isinstance(score, (int, float)):
                observed_score = True
                if score > best_score:
                    best_score, no_increase, last_increase = score, 0, step
                else:
                    no_increase += 1
                    longest_no_increase = max(longest_no_increase, no_increase)
            if action != streak_action:
                streak_action, streak_start, streak_attempts, streak_executions = action, step, 0, 0
            streak_attempts += 1
            streak_executions += bool(transition.get("executed"))
            if streak_attempts > longest_streak["attempts"]:
                longest_streak = {"action": action, "attempts": streak_attempts,
                                  "executions": streak_executions,
                                  "first_step": streak_start, "last_step": step}
            current_view = view
    return {
        "kind": "offline_episode_inspection", "episode_id": header.get("episode_id"),
        "episode_kind": header.get("kind"),
        "actor": header.get("components", {}).get("actor"),
        "behavior": {
            "action_output_validation": {p: dict(c) for p, c in validations.items()
                                         if c or p != "action_review"},
            "action_frequencies": dict(frequencies),
            "movement_attempts": movement_attempts,
            "executed_recipe_rechecks": recipe_count,
            "recipe_recheck_budget_spent": recipe_cost,
            "distinct_recipe_recheck_observations": len(recipe_observations),
            "longest_same_action_streak": longest_streak,
            "longest_no_score_increase_streak": longest_no_increase,
            "last_score_increase_step": last_increase,
            "maximum_observed_score": best_score if observed_score else None,
            "recorded_inventory_actions": inventory_actions,
        },
        "turns": turns,
        "errors": [e for e in events if e["event"] in {"episode_error", "model_error"}],
        "interpretation": "Score plateaus can include useful exploration. Command records do not "
                          "constitute an oracle inventory. Review observations before attributing failures.",
    }


def memory_metrics(events: list[dict], strategy: str, limit: int | None) -> dict:
    """Offline provenance only; absent or ambiguous legacy evidence stays unknown."""
    updates = [e for e in events if e["event"] == "memory_update"]
    if strategy == "full_history":
        return {"memory_updates": len(updates),
                "max_stored_tokens": max((u["memory_tokens"] for u in updates), default=0),
                "memory_writer_calls": sum(e["event"] == "model_request" and
                                           e.get("purpose", "").startswith("memory") for e in events),
                "token_count_method": "recorded_trace_no_recount",
                "updates": [{"sequence": u.get("sequence"), "stored_tokens": u["memory_tokens"]}
                            for u in updates]}
    counts = Counter()
    rows = []
    for update in updates:
        labels = update.get("validation_events", [])
        outcomes = [label for label in labels if label in {
            "memory_accepted", "memory_repair_accepted", "memory_fallback:previous_valid_memory"}]
        outcome = outcomes[0] if len(outcomes) == 1 else "unknown"
        counts[outcome] += 1
        empty = None
        if outcome in {"memory_accepted", "memory_repair_accepted"}:
            if strategy == "prose":
                empty = update["memory"] == ""
            elif strategy == "structured":
                try:
                    empty = json.loads(update["memory"]) == {}
                except ValueError:
                    pass
        if empty is True:
            counts["accepted_empty"] += 1
        if empty is None:
            counts["empty_unknown"] += 1
        rows.append({"sequence": update.get("sequence"), "outcome": outcome,
                     "accepted_empty": empty, "stored_tokens": update.get("memory_tokens"),
                     "utilization": update.get("memory_tokens", 0) / limit if limit else None})
    rejections = [label.split(":", 1)[1] for u in updates
                  for label in u.get("validation_events", [])
                  if label.startswith(("memory_rejected:", "memory_repair_rejected:"))]
    candidates = []
    for e in events:
        if e["event"] != "model_response" or e["purpose"] not in {"memory", "memory_repair"}:
            continue
        # Only explicit size-rejection evidence gives a rejected candidate's rendered size.
        following = next((u for u in updates if u.get("sequence", -1) > e.get("sequence", -1)
                          and u.get("step") == e.get("step")), {})
        prefix = "memory_repair_rejected:" if e["purpose"] == "memory_repair" else "memory_rejected:"
        reason = next((v[len(prefix):] for v in following.get("validation_events", [])
                       if v.startswith(prefix)), None)
        rendered = None
        if reason and reason.startswith("over_budget:"):
            try:
                rendered = int(reason.split(":")[1].split(">")[0])
            except ValueError:
                pass
        accepted = "memory_repair_accepted" if e["purpose"] == "memory_repair" else "memory_accepted"
        if accepted in following.get("validation_events", []):
            rendered = following.get("memory_tokens")
        candidates.append({"sequence": e.get("sequence"), "purpose": e["purpose"],
                           "raw_output_tokens": e.get("output_tokens"),
                           "rendered_tokens": rendered, "rejection": reason})
    format_checks = []
    for update in updates:
        adherence = None
        if strategy == "structured":
            try:
                adherence = isinstance(json.loads(update["memory"]), dict)
            except ValueError:
                adherence = False
        elif strategy == "prose":
            # A narrow offline flag, not a complete natural-language classifier.
            try:
                adherence = not isinstance(json.loads(update["memory"]), (dict, list))
            except ValueError:
                pass
        format_checks.append({"sequence": update.get("sequence"),
                              "format_adherence": adherence})
    syntax_reasons = {"memory_must_be_text", "invalid_unicode", "duplicate_json_key",
                      "nonfinite_json_number", "json_number_unrepresentable", "json_number_changed",
                      "malformed_json", "json_object_required"}
    return {"memory_updates": len(updates), "primary_accepted": counts["memory_accepted"],
            "repaired_accepted": counts["memory_repair_accepted"],
            "previous_state_fallback": counts["memory_fallback:previous_valid_memory"],
            "outcome_unknown": counts["unknown"], "accepted_empty": counts["accepted_empty"],
            "empty_unknown": counts["empty_unknown"],
            "over_budget_rejections": sum(r.startswith("over_budget:") for r in rejections),
            "syntax_rejections": sum(r in syntax_reasons for r in rejections),
            "rejection_reasons": dict(Counter(rejections)),
            "unclassified_rejections": sum(r not in syntax_reasons and not r.startswith("over_budget:") for r in rejections), "updates": rows,
            "candidates": candidates, "format_checks": format_checks, "token_count_method": "recorded_trace_no_recount"}


def audit_legal_choices(events, result, require):
    """Independent trace-derived audit. Never calls the actor or backend helpers.

    Hash format/provenance is checked here; its value needs the matching template
    and tokenizer to recompute. This audit does not establish model capability.
    """
    actor = result["components"]["actor"]
    require(result["config"]["strategy"] == "full_history" and
            actor.get("context_mode") == "full_history", "choice requires full history")
    require(actor.get("prompt_version") == "full-history-legal-choice-v1" and
            actor.get("action_output_policy") == "legal_label_argmax_v1" and
            actor.get("max_repairs") == 0 and actor.get("action_review_policy") == "none" and
            actor.get("action_repair_policy") == "none" and
            actor.get("legality_guaranteed_by_interface") is True,
            "incorrect choice actor identity")
    current, history, pending, selected = None, None, None, None
    next_step = 1
    requests = responses = actions = errors = 0
    attempted_steps = set()
    terminal = False
    episode_failed = False
    rejected_responses = 0
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    for index, event in enumerate(events):
        name = event["event"]
        require(not episode_failed or name == "episode_end",
                "choice trace continues after episode_error")
        if name == "episode_error":
            episode_failed = True
        if name == "reset":
            require(current is None, "duplicate choice reset")
            current = event["view"]
        elif name == "memory_update":
            history = event["memory"]
        elif name == "model_request":
            require(event["purpose"] == "action", "choice permits no writer/review/repair")
            require(not errors and not terminal and event["step"] not in attempted_steps,
                    "choice request retries or follows termination/error")
            attempted_steps.add(event["step"])
            require(event["step"] == next_step and pending is None and selected is None,
                    "duplicate or out-of-order choice request")
            require(current is not None and isinstance(history, str), "choice missing public evidence")
            allowed = current["allowed_actions"]
            require(0 < len(allowed) <= 52 and all(isinstance(a, str) and a for a in allowed) and
                    len(set(allowed)) == len(allowed), "invalid choice action set")
            labels = list(alphabet[:len(allowed)])
            require(event.get("inference_mode") == "legal_label_argmax_v1" and
                    event.get("labels") == labels, "choice request labels disagree")
            messages = event["messages"]
            require(len(messages) == 2 and [m["role"] for m in messages] == ["system", "user"] and
                    all(set(m) == {"role", "content"} for m in messages), "unexpected choice messages")
            require(set(current) == {"observation", "goal", "allowed_actions", "budget_remaining", "recheck_cost"},
                    "choice public view contains unexpected fields")
            system = messages[0]["content"]
            # Frozen v31 full-history fixture system, with only the specified
            # output sentence replaced. Independent of the production builder.
            require(sha256(system.encode("utf-8")).hexdigest() == "1c3f432235de9a58bdee3639666f7de1e3ae44a8c9f86e8e73a6c5090f33dbe1",
                    "choice system guidance changed or annotated")
            require(system.count("Return only the label of one listed legal action option, with no other text.") == 1 and
                    "Return JSON with next_direction, missing_prerequisite, action." not in system,
                    "choice output instruction disagrees")
            # Reconstruct the public serialization independently, including literal
            # history and the complete ordered option list. No split can confuse
            # a footer-like string inside an observation or history record.
            options = [{"label": label, "action": action} for label, action in zip(labels, allowed)]
            expected = ("Current game input:\n" + json.dumps(current, sort_keys=True) +
                        "\nVisible interaction history (diagnostic):\n" + history +
                        "\nLegal action options (legal-choice-v1):\n" +
                        json.dumps(options, ensure_ascii=False, sort_keys=True))
            require(messages[1]["content"] == expected, "choice mapping/public view/history disagrees")
            pending = (labels, allowed)
            requests += 1
        elif name == "model_response":
            require(pending is not None and event["purpose"] == "action" and event["step"] == next_step,
                    "unexpected choice response")
            labels, allowed = pending
            m = event["metadata"]
            require(m.get("inference_mode") == "legal_label_argmax_v1" and
                    m.get("generation_called") is False and m.get("labels") == labels,
                    "choice response labels/mode disagree")
            ids, logits, probs = (m["label_token_ids"], m["candidate_logits"], m["conditional_probabilities"])
            require(all(isinstance(a, list) and len(a) == len(labels) for a in (ids, logits, probs)),
                    "choice score arrays misaligned")
            require(all(type(t) is int and t >= 0 for t in ids) and len(set(ids)) == len(ids),
                    "invalid choice token IDs")
            require(all(type(x) in (float, int) and math.isfinite(x) for x in logits + probs),
                    "nonfinite/missing choice scores")
            largest = max(logits)
            weights = [math.exp(x - largest) for x in logits]
            total = sum(weights)
            require(all(p >= 0 and math.isclose(p, w / total, rel_tol=1e-6, abs_tol=1e-8)
                        for p, w in zip(probs, weights)), "choice probabilities disagree with logits")
            winner = logits.index(largest)
            require(event["text"] == m.get("selected_label") == labels[winner] and
                    m.get("selected_token_id") == ids[winner], "choice argmax/label disagrees")
            require(m.get("selection_rule") == "argmax" and m.get("tie_break") == "first_in_supplied_order" and
                    m.get("finish_reason") == "choice" and m.get("decision_token_count") == 1, "choice decision accounting disagrees")
            require(type(event["input_tokens"]) is int and event["input_tokens"] > 0 and
                    type(event["elapsed_seconds"]) in (int, float) and
                    math.isfinite(event["elapsed_seconds"]) and event["elapsed_seconds"] >= 0,
                    "invalid choice usage")
            fake = result["components"]["model"].get("is_fake") is True
            if fake:
                require(m.get("scoring_evidence") == "synthetic_fixture" and m.get("is_fake") is True and
                        m.get("rendered_prompt_sha256") is None and
                        m.get("prompt_hash_evidence") == "unavailable_fixture" and
                        m.get("token_accounting") == "synthetic_fixture_ids_and_whitespace_counts_not_Qwen" and
                        m.get("latency_scope") == "synthetic_fixture_zero_not_measured",
                        "fixture choice evidence is not explicit")
            else:
                require(m.get("scoring_evidence") == "actual_model_forward" and
                        m.get("prompt_hash_evidence") == "actual_rendered_prompt" and
                        isinstance(m.get("rendered_prompt_sha256"), str) and
                        re.fullmatch(r"[0-9a-f]{64}", m["rendered_prompt_sha256"]) is not None,
                        "actual rendered prompt hash evidence required")
                special_ids = m.get("special_token_ids")
                require(isinstance(special_ids, list) and
                        all(type(t) is int and t >= 0 for t in special_ids) and
                        special_ids == sorted(set(special_ids)),
                        "invalid or missing special-token inventory")
                require(set(ids).isdisjoint(special_ids), "choice label is a special token")
                require(type(m.get("output_vocab_size")) is int and
                        all(t < m["output_vocab_size"] for t in ids), "choice token outside vocabulary")
                require(m.get("latency_scope") ==
                        "synchronized_forward_excludes_tokenization_validation_transfer_cpu_selection",
                        "incorrect choice latency scope")
            if event["output_tokens"] != 1:
                following = events[index + 1:]
                require(len(following) == 2 and
                        following[0].get("event") == "episode_error" and
                        following[0].get("step") == event["step"] and
                        following[0].get("phase") == "action_generation" and
                        following[0].get("error_type") == "ValueError" and
                        following[0].get("error_message") ==
                        "choice scoring must report one decision token" and
                        following[1].get("event") == "episode_end" and
                        result["status"] == "error",
                        "unexpected choice output count lacks matching terminal error")
                rejected_responses += 1
            else:
                selected = allowed[winner]
            pending = None
            responses += 1
        elif name == "model_error":
            require(pending is not None and event["purpose"] == "action" and event["step"] == next_step,
                    "unexpected choice model error")
            pending = None
            errors += 1
        elif name == "action":
            require(selected is not None and pending is None and event["step"] == next_step,
                    "choice action without one scoring decision")
            require(event["transition"]["action"] == selected, "choice canonical action disagrees")
            current = event["transition"]["view"]
            terminal = event["transition"]["terminated"] or event["transition"]["truncated"]
            selected = None
            next_step += 1
            actions += 1
    require(pending is None and requests == responses + errors, "unfinished choice scoring")
    require(responses == actions + int(selected is not None) + rejected_responses, "choice decisions/actions disagree")
    require(result["status"] == "error" or (selected is None and errors == 0),
            "completed choice episode has unfinished/error decision")
    require(sum(e["event"] == "episode_start" for e in events) == 1 and
            sum(e["event"] == "episode_end" for e in events) == 1,
            "duplicate choice episode events")
    episode_errors = [e for e in events if e["event"] == "episode_error"]
    require(len(episode_errors) == int(result["status"] == "error"), "choice error event count disagrees")
    if episode_errors:
        require(result["failure"] is None and all(episode_errors[0].get(k) == v
                for k, v in result["error"].items()), "choice error record disagrees")
    else:
        require(terminal, "choice completion lacks a terminal transition")
    for purpose, usage in result["usage_by_purpose"].items():
        require(math.isclose(usage["elapsed_seconds"], sum(e["elapsed_seconds"] for e in events
                    if e["event"] == "model_response" and e["purpose"] == purpose)),
                "choice purpose latency disagrees")


def summarize(root: Path, *, include_fixtures: bool = False) -> dict:
    directories = sorted({p.parent for pattern in ("events.jsonl", "result.json")
                          for p in root.rglob(pattern)})
    if not directories:
        raise ValueError("no episode traces or results found")
    episodes, issues, pending, fingerprints, identities = [], [], [], set(), set()
    for directory in directories:
        label = str(directory.relative_to(root))
        if not (directory / "result.json").exists():
            pending.append(label)
            continue
        try:
            result = json.loads((directory / "result.json").read_text())
            events = [json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines()]

            def require(condition, message):
                if not condition:
                    raise ValueError(message)

            choice_policy = result["components"]["actor"].get("implementation") == "LegalChoiceActor"
            strategy = result["config"]["strategy"]
            require(strategy in {"full_history", "prose", "structured"},
                    "unknown memory strategy")
            fixture = any(c.get("is_fake") is not False for c in result["components"].values())
            require(include_fixtures or not fixture, "fixture excluded; use --include-fixtures only for plumbing checks")
            expected_kind = ("integration_fixture" if fixture else
                             "full_history_diagnostic" if strategy == "full_history" else
                             "evaluation" if result["config"]["game"]["game_fold"] == "test"
                             else "development")
            require(result["kind"] == expected_kind,
                    "component labels disagree with result kind")
            require(events and events[0]["event"] == "episode_start", "missing episode_start")
            require(events[-1]["event"] == "episode_end", "missing episode_end")
            require(events[-1]["result"] == result, "result disagrees with trace")
            require([e["sequence"] for e in events] == list(range(len(events))), "broken event sequence")
            require(events[0]["config"] == result["config"] and
                    events[0]["components"] == result["components"], "header disagrees with result")
            require(events[0].get("protocol_id") == result.get("protocol_id"), "protocol identity disagrees with trace")
            require(events[0].get("source") == result.get("source"), "source identity disagrees with trace")
            require(events[0].get("memory_token_limit_applies") is (strategy != "full_history"),
                    "memory token-limit policy is not explicit")
            actions = [e["transition"] for e in events if e["event"] == "action"]
            replies = [e for e in events if e["event"] == "model_response"]
            require(result["steps"] == len(actions), "step total disagrees with trace")
            require(result["budget_spent"] == sum(a["action_cost"] for a in actions), "budget total disagrees with trace")
            require(result["recipe_rechecks"] == sum(a["recipe_recheck"] for a in actions), "reread total disagrees with trace")
            for field in ("input_tokens", "output_tokens"):
                require(result[field] == sum(e[field] for e in replies), f"{field} total disagrees with trace")
            require(math.isclose(result["model_elapsed_seconds"],
                                 sum(e["elapsed_seconds"] for e in replies)),
                    "model latency total disagrees with trace")
            require(set(result["usage_by_purpose"]) == {e["purpose"] for e in replies},
                    "usage purpose labels disagree with trace")
            for purpose, usage in result["usage_by_purpose"].items():
                selected = [e for e in replies if e["purpose"] == purpose]
                require(usage["calls"] == len(selected), "purpose call total disagrees with trace")
                for field in ("input_tokens", "output_tokens"):
                    require(usage[field] == sum(e[field] for e in selected),
                            f"purpose {field} total disagrees with trace")
            request = None
            model_errors = 0
            for event in events:
                if event["event"] == "model_request":
                    require(request is None, "unmatched model request")
                    request = (event["step"], event["purpose"])
                elif event["event"] in {"model_response", "model_error"}:
                    require(request == (event["step"], event["purpose"]), "unmatched model response/error")
                    request = None
                    model_errors += event["event"] == "model_error"
            require(request is None, "unfinished model request")
            require(result["usage_complete"] == (model_errors == 0), "incorrect usage completeness")
            updates = [e for e in events if e["event"] == "memory_update"]
            if result["components"]["memory"].get("prompt_version") == "p1-memory-v17":
                require(memory_metrics(events, strategy, result["config"].get("memory_token_limit"))["outcome_unknown"] == 0,
                        "v17 memory updates require exactly one final acceptance/fallback outcome")
            memory_replies = [e for e in replies if e["purpose"].startswith("memory")]
            latest_memory_by_request = {}
            latest_memory = None
            for event in events:
                if event["event"] == "memory_update":
                    latest_memory = event["memory"]
                elif (event["event"] == "model_request"
                      and event["purpose"] in {"action", "action_review", "action_repair"}):
                    latest_memory_by_request[event["sequence"]] = latest_memory
            archive_context = (
                strategy == "full_history" and result["components"]["memory"].get("implementation") == "FullHistoryMemory")
            memory_requests = [e for e in events if e["event"] == "model_request"
                               and e["purpose"].startswith("memory")]
            if strategy == "full_history":
                require(not memory_requests and not memory_replies,
                        "public-history condition unexpectedly ran a memory writer request/response")
            else:
                limit = result["config"]["memory_token_limit"]
                require(bool(memory_requests) or result["status"] == "error",
                        "bounded-memory episode has no writer calls")
                require(all(type(e["memory_tokens"]) is int and 0 <= e["memory_tokens"] <= limit
                            for e in updates), "rendered memory exceeds its declared token allowance")
                require(sum(e["purpose"] == "memory" for e in memory_replies) == len(updates) +
                        int(result["status"] == "error" and any(
                            e["purpose"] == "memory" and e["step"] not in {u["step"] for u in updates}
                            for e in memory_replies)),
                        "memory update count disagrees with primary writer calls")
                for event in events:
                    if event["event"] != "model_request" or not event["purpose"].startswith("memory"):
                        continue
                    require(len(event["messages"]) in {2, 4},
                            "memory writer received unexpected message history")
                    payload = json.loads(event["messages"][1]["content"])
                    require(set(payload) == ({"previous_memory", "action", "observation", "context", "strategy"}
                                            if fixture and result["components"]["memory"].get("implementation") == "FakeMemory"
                                            else {"previous_memory", "action", "observation", "context"}),
                            "memory writer input contains unexpected fields")
                    require(set(payload["context"]) == {"goal", "budget_remaining", "recheck_cost",
                                                         "memory_token_limit"},
                            "memory writer context contains unexpected fields")
            public_by_request, writer_by_request = {}, {}
            current_view, previous_text, records = None, None, []
            pending_record = None
            spent = 0
            for event in events:
                name = event["event"]
                if name == "reset":
                    current_view = event["view"]
                    require(current_view["budget_remaining"] == result["config"]["action_budget"],
                            "reset budget disagrees with configuration")
                    previous_text = "[]" if strategy == "full_history" else ("" if strategy == "prose" else "{}")
                    pending_record = {"action": "[INITIAL_OBSERVATION]", "observation": current_view["observation"]}
                elif name == "action" and current_view is not None:
                    transition = event["transition"]
                    require(event["memory_before_action"] == previous_text, "action used stale memory")
                    legal = transition["action"] in current_view["allowed_actions"]
                    reread = legal and transition["action"] in {"read cookbook", "examine cookbook"}
                    cost = result["config"]["recheck_cost"] if reread else 1
                    affordable = cost <= current_view["budget_remaining"]
                    require(transition["valid_action"] == legal and transition["executed"] == (legal and affordable),
                            "action legality/execution disagrees with public view")
                    require(transition["action_cost"] == (cost if affordable else 0), "action cost disagrees with price")
                    require(transition["recipe_recheck"] == (reread and affordable), "reread classification disagrees")
                    spent += transition["action_cost"]
                    current_view = transition["view"]
                    require(current_view["budget_remaining"] == result["config"]["action_budget"] - spent,
                            "remaining budget disagrees with action ledger")
                    pending_record = (None if transition["terminated"] or transition["truncated"] else
                                      {"action": transition["action"], "observation": current_view["observation"]})
                elif name == "memory_update" and current_view is not None:
                    require(pending_record is not None and event["action"] == pending_record["action"],
                            "unexpected memory update or missing public action")
                    require(event["previous_memory"] == previous_text, "memory update used stale memory")
                    if strategy == "full_history":
                        records.append(pending_record)
                        require(event["memory"] == json.dumps(records, ensure_ascii=False),
                                "full history disagrees with actual public records")
                    previous_text, pending_record = event["memory"], None
                elif name == "model_request" and current_view is not None:
                    if event["purpose"].startswith("action"):
                        require(pending_record is None, "actor requested before updating public evidence")
                        public_by_request[event["sequence"]] = current_view
                    elif event["purpose"].startswith("memory"):
                        require(pending_record is not None, "writer requested without new public evidence")
                        writer_by_request[event["sequence"]] = {
                            "previous_memory": previous_text, **pending_record,
                            "context": {"goal": current_view["goal"],
                                        "budget_remaining": current_view["budget_remaining"],
                                        "recheck_cost": current_view["recheck_cost"],
                                        "memory_token_limit": result["config"]["memory_token_limit"]}}
            if result["status"] == "completed" and current_view is not None:
                require(pending_record is None, "completed episode missed a memory update")
            for event in memory_requests:
                require(event["sequence"] in writer_by_request, "writer request has no preceding public view")
                if event["sequence"] in writer_by_request:
                    payload = json.loads(event["messages"][1]["content"])
                    if fixture and result["components"]["memory"].get("implementation") == "FakeMemory":
                        require(payload.pop("strategy") == strategy, "fixture writer strategy disagrees")
                    require(payload == writer_by_request[event["sequence"]],
                            "writer input disagrees with latest public evidence")
            if choice_policy:
                audit_legal_choices(events, result, require)
            for event in events:
                if choice_policy:
                    continue
                if event["event"] != "model_request" or event["purpose"] not in {"action", "action_review", "action_repair"}:
                    continue
                require(len(event["messages"]) in {2, 4}, "actor received unexpected conversation history")
                user = event["messages"][1]["content"]
                context_label = ("\nVisible interaction history (diagnostic):\n" if archive_context else "\nBounded memory:\n")
                public, rendered = user.split(context_label, maxsplit=1)
                payload = json.loads(public.removeprefix("Current game input:\n"))
                require(set(payload) == {"observation", "goal", "allowed_actions",
                                         "budget_remaining", "recheck_cost"},
                        "bounded actor input contains unexpected fields")
                require(event["sequence"] in public_by_request, "actor request has no preceding public view")
                require(payload == public_by_request[event["sequence"]],
                        "actor public view disagrees with public trace")
                latest = latest_memory_by_request[event["sequence"]]
                require(isinstance(latest, str), "actor has no latest retained history/memory update")
                if rendered != latest:
                    prefix = latest + "\nPrevious unavailable proposal: "
                    require(event["purpose"] in {"action_repair", "action_review"} and
                            result["components"]["actor"].get("action_repair_policy") in {
                                FINALIZATION_REPAIR_POLICY} and
                            rendered.startswith(prefix),
                            "actor input disagrees with the latest bounded memory update")
                    proposal = rendered[len(prefix):]
                    preceding = [response for response in replies
                                 if response["step"] == event["step"] and
                                 response["sequence"] < event["sequence"] and
                                 response["purpose"] in {"action", "action_review"}]
                    require(any(validate_action_output(response["text"],
                                                       payload["allowed_actions"])[0] == proposal
                                for response in preceding),
                            "actor repair proposal was not recorded in this turn")
            require(result["status"] in {"completed", "error"}, "unknown episode status")
            if result["status"] == "completed":
                require(bool(actions) and actions[-1]["termination_reason"] == result["termination_reason"],
                        "completed episode has no matching terminal action")
                require(result["success"] == actions[-1]["success"], "success disagrees with trace")
            else:
                require(result["success"] is None and result["error"] is not None,
                        "infrastructure error must not be labeled a game loss")
            config = {k: v for k, v in result["config"].items() if k != "seed"}
            model = {k: v for k, v in result["components"]["model"].items() if k != "load_seconds"}
            fingerprint = json.dumps({"config": config, "model": model,
                                      "actor": result["components"]["actor"],
                                      "memory": result["components"]["memory"],
                                      "source": result.get("source"),
                                      "protocol_id": result.get("protocol_id")}, sort_keys=True)
            fingerprints.add(fingerprint)
            identity = (fingerprint, result["config"]["seed"])
            require(identity not in identities, "duplicate game seed/configuration; use a separate attempt directory")
            identities.add(identity)
            episodes.append({
                "directory": label, "episode_id": result["episode_id"],
                "kind": result["kind"], "seed": result["config"]["seed"],
                "status": result["status"], "success": result["success"],
                "termination_reason": result["termination_reason"], "error": result["error"],
                "steps": result["steps"], "budget_spent": result["budget_spent"],
                "score": result.get("score"), "usage_complete": result["usage_complete"],
                "usage_by_purpose": result["usage_by_purpose"],
                "generation_by_purpose": {
                    purpose: {"calls": sum(e["event"] == "model_request" and e.get("purpose") == purpose for e in events),
                              "returned_calls": sum(e["purpose"] == purpose for e in replies),
                              "failed_calls": sum(e["event"] == "model_error" and e.get("purpose") == purpose for e in events),
                              "input_tokens": sum(e["input_tokens"] for e in replies if e["purpose"] == purpose),
                              "output_tokens": sum(e["output_tokens"] for e in replies if e["purpose"] == purpose),
                              "elapsed_seconds": sum(e["elapsed_seconds"] for e in replies if e["purpose"] == purpose),
                              "limit_hits": sum(e.get("metadata", {}).get("finish_reason") == "length"
                                                for e in replies if e["purpose"] == purpose)}
                    for purpose in sorted({e["purpose"] for e in events
                                           if e["event"] in {"model_request", "model_response", "model_error"}})},
                "load_seconds": result["components"]["model"].get("load_seconds"),
                "launcher_exit_status": None,
                "memory_evidence": memory_metrics(events, strategy, result["config"].get("memory_token_limit")),
                "recipe_rechecks": result["recipe_rechecks"],
                "invalid_actions": sum(not a["valid_action"] for a in actions),
                "action_repair_calls": sum(e["purpose"] == "action_repair" for e in replies),
                "output_limit_hits": sum(e.get("metadata", {}).get("finish_reason") == "length" for e in replies),
                "input_tokens": result["input_tokens"], "output_tokens": result["output_tokens"],
                "model_elapsed_seconds": result["model_elapsed_seconds"],
                "runtime_seconds": result["runtime_seconds"],
                "actor_prompt": result["components"]["actor"].get("prompt_version"),
                "memory_strategy": strategy,
                "memory_calls": sum(e["purpose"] == "memory" for e in memory_replies),
                "memory_repair_calls": sum(e["purpose"] == "memory_repair" for e in memory_replies),
                "max_memory_tokens": max((e["memory_tokens"] for e in updates), default=0),
                **({"legality_guaranteed_by_interface": True} if choice_policy else {}),
                "fixture": fixture,
                "behavior": analyze_events(events)["behavior"],
                "turns": analyze_events(events)["turns"],
                "errors": analyze_events(events)["errors"],
            })
        except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
            issues.append({"directory": label, "error": str(error)})
    if len(fingerprints) > 1:
        issues.append({"directory": ".", "error": "mixed configurations or source identities; summarize each pilot separately"})
    real = [e for e in episodes if not e["fixture"]]
    completed = [e for e in real if e["status"] == "completed"]
    clean = not issues and not pending
    return {
        "kind": ("full_history_checkpoint_report" if real and
                 all(e["memory_strategy"] == "full_history" for e in real)
                 else "bounded_memory_checkpoint_report"), "logging_checks_passed": clean,
        "real_model_capability_tested": bool(completed),
        "infrastructure_checks_passed": clean and bool(completed) and len(completed) == len(real),
        "real_completed": len(completed), "real_successes": sum(e["success"] is True for e in completed),
        "real_infrastructure_errors": len(real) - len(completed),
        "fixture_episodes": len(episodes) - len(real),
        "termination_counts": dict(Counter(e["termination_reason"] for e in real)),
        "issues": issues, "pending": pending, "episodes": episodes,
        "interpretation": "Inspect traces for gameplay, planning, and information-use failures. "
                          "This report does not establish memory-strategy effectiveness or statistical significance.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--include-fixtures", action="store_true")
    args = parser.parse_args()
    try:
        report = summarize(args.root, include_fixtures=args.include_fixtures)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2, sort_keys=True))
    # Gameplay losses are data. Broken logs, pending runs, and infrastructure
    # errors fail this technical checkpoint, independently of capability.
    return 0 if (report["logging_checks_passed"] and not report["real_infrastructure_errors"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
