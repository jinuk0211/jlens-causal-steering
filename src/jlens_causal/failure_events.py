"""General TauBench failure localization and paired replay planning.

The official Tau2 reviewer supplies actor, error tags, and ``turn_idx``.  We
validate those labels against the serialized trajectory and combine them with
deterministic tool/protocol signals.  Task ``evaluation_criteria.actions`` are
deliberately ignored here because TauBench normally treats them as one valid
reference trajectory, not the only correct sequence.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

FAILURE_EVENT_SCHEMA = "agent-failure-event-v1"
FAILURE_REPLAY_SCHEMA = "agent-failure-replay-plan-v1"
DETECTOR_VERSION = "tau2-review-plus-structural-v1"

Actor = Literal["agent", "user", "system", "unknown"]
Source = Literal["tau2_review", "structural", "outcome"]

_ERROR_TERMINATIONS = {
    "agent_error",
    "infrastructure_error",
    "max_steps",
    "timeout",
    "too_many_errors",
}
_REVIEW_TAG_PRIORITY = (
    "wrong_sequence",
    "tool_call_schema_error",
    "tool_call_argument_error",
    "irrelevant_tool_call",
    "missed_required_action",
    "premature_termination",
    "guideline_violation",
    "incorrect_interpretation",
    "hallucination",
    "revealed_info_early",
    "inconsistent_behavior",
    "other",
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _stable_id(*parts: Any) -> str:
    payload = "\0".join(_canonical_json(part) for part in parts)
    return hashlib.sha256(payload.encode()).hexdigest()[:24]


def _excerpt(value: Any, limit: int = 240) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _turn(message: dict[str, Any]) -> int | None:
    value = message.get("turn_idx")
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _find_turn(
    messages: Sequence[dict[str, Any]], turn_idx: int | None, actor: Actor
) -> tuple[int | None, dict[str, Any] | None, bool]:
    if turn_idx is None:
        return None, None, False
    candidates = [
        (index, message) for index, message in enumerate(messages) if _turn(message) == turn_idx
    ]
    if not candidates:
        return None, None, False
    expected_role = {"agent": "assistant", "user": "user"}.get(actor)
    for index, message in candidates:
        if expected_role is None or message.get("role") == expected_role:
            return index, message, True
    index, message = candidates[0]
    return index, message, expected_role is None


@dataclass(frozen=True)
class FailureEvent:
    """One auditable failure label at a trajectory decision boundary."""

    event_id: str
    simulation_id: str
    task_id: str
    trial: int
    actor: Actor
    category: str
    severity: str | None
    first_bad_turn: int | None
    first_bad_message_index: int | None
    trigger_turn: int | None
    evidence_message_indices: tuple[int, ...]
    reasoning: str
    correct_behavior: str | None
    sources: tuple[Source, ...]
    confidence: float
    detector_version: str = DETECTOR_VERSION
    review_tags: tuple[str, ...] = ()
    evidence_excerpt: str = ""

    @property
    def steerable(self) -> bool:
        return self.actor == "agent" and self.first_bad_turn is not None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["schema_version"] = FAILURE_EVENT_SCHEMA
        value["steerable"] = self.steerable
        return value


def _make_event(
    simulation: dict[str, Any],
    *,
    actor: Actor,
    category: str,
    severity: str | None,
    turn_idx: int | None,
    message_index: int | None,
    reasoning: str,
    sources: Iterable[Source],
    evidence: Iterable[int] = (),
    trigger_turn: int | None = None,
    correct_behavior: str | None = None,
    confidence: float = 1.0,
    review_tags: Iterable[str] = (),
    excerpt: str = "",
) -> FailureEvent:
    simulation_id = str(simulation.get("id", ""))
    task_id = str(simulation.get("task_id", ""))
    trial = int(simulation.get("trial", 0) or 0)
    evidence_tuple = tuple(sorted(set(int(index) for index in evidence)))
    source_tuple = tuple(sorted(set(sources)))
    tag_tuple = tuple(dict.fromkeys(str(tag) for tag in review_tags if tag))
    return FailureEvent(
        event_id=_stable_id(
            FAILURE_EVENT_SCHEMA,
            simulation_id,
            actor,
            category,
            turn_idx,
            message_index,
            evidence_tuple,
        ),
        simulation_id=simulation_id,
        task_id=task_id,
        trial=trial,
        actor=actor,
        category=category,
        severity=severity,
        first_bad_turn=turn_idx,
        first_bad_message_index=message_index,
        trigger_turn=turn_idx if trigger_turn is None else trigger_turn,
        evidence_message_indices=evidence_tuple,
        reasoning=reasoning,
        correct_behavior=correct_behavior,
        sources=source_tuple,
        confidence=max(0.0, min(1.0, float(confidence))),
        review_tags=tag_tuple,
        evidence_excerpt=excerpt,
    )


def _review_category(tags: Sequence[Any]) -> str:
    normalized = [str(tag) for tag in tags if tag]
    for candidate in _REVIEW_TAG_PRIORITY:
        if candidate in normalized:
            return candidate
    return normalized[0] if normalized else "review_error"


def review_failure_events(simulation: dict[str, Any]) -> list[FailureEvent]:
    """Import official ``tau2 review --mode full`` errors."""

    review = simulation.get("review")
    if not isinstance(review, dict):
        return []
    messages = simulation.get("messages") or []
    events: list[FailureEvent] = []
    for error in review.get("errors") or []:
        if not isinstance(error, dict) or error.get("source") == "unknown":
            continue
        raw_actor = str(error.get("source", "unknown"))
        actor: Actor = raw_actor if raw_actor in {"agent", "user"} else "unknown"
        try:
            turn_idx = None if error.get("turn_idx") is None else int(error["turn_idx"])
        except (TypeError, ValueError):
            turn_idx = None
        message_index, message, actor_matches = _find_turn(messages, turn_idx, actor)
        tags = error.get("error_tags") or []
        if isinstance(tags, str):
            tags = [tags]
        category = _review_category(tags)
        # A reviewer-only wrong_sequence label is deliberately weaker because
        # the example action trajectory is not guaranteed to be unique.
        confidence = 0.65 if category == "wrong_sequence" else 0.85
        if not actor_matches:
            confidence = min(confidence, 0.45)
        reasoning = str(error.get("reasoning") or "Tau2 review detected an error.")
        if turn_idx is not None and message_index is None:
            reasoning += " The reported turn is absent from the serialized messages."
        elif not actor_matches:
            reasoning += " The reported actor does not match the role at that turn."
        events.append(
            _make_event(
                simulation,
                actor=actor,
                category=category,
                severity=error.get("severity"),
                turn_idx=turn_idx,
                message_index=message_index,
                evidence=() if message_index is None else (message_index,),
                reasoning=reasoning,
                correct_behavior=error.get("correct_behavior"),
                sources=("tau2_review",),
                confidence=confidence,
                review_tags=tags,
                excerpt=_excerpt(message.get("content") if message else ""),
            )
        )
    return events


@dataclass(frozen=True)
class _Call:
    message_index: int
    turn_idx: int | None
    call_id: str | None
    name: str
    arguments: dict[str, Any]
    fingerprint: str


def _calls(messages: Sequence[dict[str, Any]]) -> list[_Call]:
    values: list[_Call] = []
    for index, message in enumerate(messages):
        if message.get("role") != "assistant":
            continue
        for call in message.get("tool_calls") or []:
            if not isinstance(call, dict):
                continue
            arguments = call.get("arguments")
            if not isinstance(arguments, dict):
                arguments = {"__raw__": arguments}
            name = str(call.get("name", ""))
            values.append(
                _Call(
                    message_index=index,
                    turn_idx=_turn(message),
                    call_id=None if call.get("id") in (None, "") else str(call["id"]),
                    name=name,
                    arguments=arguments,
                    fingerprint=f"{name}:{_canonical_json(arguments)}",
                )
            )
    return values


def _results(messages: Sequence[dict[str, Any]]) -> list[tuple[int, dict[str, Any]]]:
    values: list[tuple[int, dict[str, Any]]] = []
    for index, message in enumerate(messages):
        if message.get("role") != "tool":
            continue
        nested = message.get("tool_messages")
        candidates = nested if isinstance(nested, list) else [message]
        values.extend(
            (index, candidate)
            for candidate in candidates
            if isinstance(candidate, dict)
            and candidate.get("requestor", "assistant") == "assistant"
        )
    return values


def _protocol_events(
    simulation: dict[str, Any], messages: Sequence[dict[str, Any]]
) -> list[FailureEvent]:
    events: list[FailureEvent] = []
    for index, message in enumerate(messages):
        role = message.get("role")
        if role not in {"assistant", "user"}:
            continue
        content = message.get("content")
        has_content = isinstance(content, str) and bool(content.strip())
        has_calls = bool(message.get("tool_calls") or [])
        if has_content and has_calls:
            category = "mixed_content_and_tool_call"
            reasoning = "A Tau2 message must contain text or tool calls, not both."
        elif not has_content and not has_calls:
            category = "empty_message"
            reasoning = "A Tau2 agent/user message may not be empty."
        else:
            continue
        actor: Actor = "agent" if role == "assistant" else "user"
        events.append(
            _make_event(
                simulation,
                actor=actor,
                category=category,
                severity="critical",
                turn_idx=_turn(message),
                message_index=index,
                evidence=(index,),
                reasoning=reasoning,
                correct_behavior="Emit exactly one of text content or a tool call.",
                sources=("structural",),
                excerpt=_excerpt(content),
            )
        )
    return events


def structural_failure_events(simulation: dict[str, Any]) -> list[FailureEvent]:
    """Detect explicit tool, retry, loop, and protocol failures."""

    messages = simulation.get("messages") or []
    calls = _calls(messages)
    results = _results(messages)
    calls_by_id = {call.call_id: call for call in calls if call.call_id is not None}
    results_by_id = {
        str(result.get("id")): (index, result)
        for index, result in results
        if result.get("id") not in (None, "")
    }
    events = _protocol_events(simulation, messages)

    for result_index, result in results:
        if not bool(result.get("error")):
            continue
        call = calls_by_id.get(str(result.get("id")))
        index = call.message_index if call else result_index
        turn_idx = call.turn_idx if call else _turn(result)
        evidence = (index, result_index) if call else (result_index,)
        events.append(
            _make_event(
                simulation,
                actor="agent",
                category="tool_call_error",
                severity="critical",
                turn_idx=turn_idx,
                message_index=index,
                evidence=evidence,
                reasoning="The environment explicitly marked the tool result as an error.",
                correct_behavior="Correct the tool choice or arguments before retrying.",
                sources=("structural",),
                excerpt=_excerpt(result.get("content")),
            )
        )

    for call in calls:
        if call.call_id is not None and call.call_id in results_by_id:
            continue
        events.append(
            _make_event(
                simulation,
                actor="agent",
                category="unresolved_tool_call",
                severity="critical",
                turn_idx=call.turn_idx,
                message_index=call.message_index,
                evidence=(call.message_index,),
                reasoning="The tool call has no matching serialized result.",
                correct_behavior="Wait for and incorporate the corresponding tool result.",
                sources=("structural",),
                excerpt=f"{call.name} {_canonical_json(call.arguments)}",
            )
        )

    fingerprints = [call.fingerprint for call in calls]
    for position in range(1, len(calls)):
        if fingerprints[position] != fingerprints[position - 1]:
            continue
        previous, current = calls[position - 1], calls[position]
        previous_result = results_by_id.get(previous.call_id or "")
        after_error = bool(previous_result and previous_result[1].get("error"))
        evidence = [previous.message_index, current.message_index]
        if previous_result:
            evidence.append(previous_result[0])
        events.append(
            _make_event(
                simulation,
                actor="agent",
                category="retry_without_state_change" if after_error else "repeated_tool_call",
                severity="critical" if after_error else "minor",
                turn_idx=current.turn_idx,
                message_index=current.message_index,
                trigger_turn=previous.turn_idx,
                evidence=evidence,
                reasoning=(
                    "The exact tool call was retried after an explicit error without revision."
                    if after_error
                    else "The exact tool call was issued on consecutive agent decisions."
                ),
                correct_behavior="Use the result to stop, revise the arguments, or choose a new action.",
                sources=("structural",),
                excerpt=f"{current.name} {_canonical_json(current.arguments)}",
            )
        )

    for period in (2, 3):
        for end in range(period * 2, len(calls) + 1):
            if fingerprints[end - 2 * period : end - period] != fingerprints[end - period : end]:
                continue
            block = calls[end - 2 * period : end]
            current = block[-1]
            events.append(
                _make_event(
                    simulation,
                    actor="agent",
                    category="short_tool_cycle",
                    severity="critical",
                    turn_idx=current.turn_idx,
                    message_index=current.message_index,
                    trigger_turn=calls[end - period].turn_idx,
                    evidence=(call.message_index for call in block),
                    reasoning=f"A tool-call block of period {period} repeated without convergence.",
                    correct_behavior="Break the cycle using new state or stop after completion.",
                    sources=("structural",),
                    excerpt=" -> ".join(call.name for call in block),
                )
            )

    reason = str(simulation.get("termination_reason") or "")
    if reason in _ERROR_TERMINATIONS:
        last_agent = next(
            (
                (index, message)
                for index, message in reversed(list(enumerate(messages)))
                if message.get("role") == "assistant"
            ),
            (None, None),
        )
        index, message = last_agent
        events.append(
            _make_event(
                simulation,
                actor=(
                    "agent"
                    if reason in {"agent_error", "max_steps", "too_many_errors"}
                    else "system"
                ),
                category=f"termination_{reason}",
                severity="critical",
                turn_idx=_turn(message) if message else None,
                message_index=index,
                evidence=() if index is None else (index,),
                reasoning=(
                    f"The simulation terminated with {reason!r}; the last turn is context, "
                    "not a proven root cause."
                ),
                sources=("structural",),
                confidence=0.45,
                excerpt=_excerpt(message.get("content") if message else ""),
            )
        )
    return events


def outcome_failure_events(simulation: dict[str, Any]) -> list[FailureEvent]:
    """Record reward failure without fabricating a causal turn."""

    reward_info = simulation.get("reward_info")
    if not isinstance(reward_info, dict):
        return []
    try:
        failed = float(reward_info.get("reward")) < 1.0
    except (TypeError, ValueError):
        return []
    if not failed:
        return []
    return [
        _make_event(
            simulation,
            actor="unknown",
            category="task_failure_unlocalized",
            severity="critical",
            turn_idx=None,
            message_index=None,
            reasoning="Reward is below 1.0; this outcome alone does not identify a causal turn.",
            sources=("outcome",),
        )
    ]


def _merge(events: Iterable[FailureEvent]) -> list[FailureEvent]:
    groups: dict[tuple[Any, ...], list[FailureEvent]] = defaultdict(list)
    for event in events:
        groups[
            (
                event.simulation_id,
                event.actor,
                event.category,
                event.first_bad_turn,
                event.first_bad_message_index,
            )
        ].append(event)
    merged: list[FailureEvent] = []

    def sort_key(value: tuple[Any, ...]) -> tuple[str, ...]:
        return tuple("" if item is None else str(item) for item in value)

    for key in sorted(groups, key=sort_key):
        values = groups[key]
        first = values[0]
        merged.append(
            _make_event(
                {"id": first.simulation_id, "task_id": first.task_id, "trial": first.trial},
                actor=first.actor,
                category=first.category,
                severity=next((value.severity for value in values if value.severity), None),
                turn_idx=first.first_bad_turn,
                message_index=first.first_bad_message_index,
                trigger_turn=first.trigger_turn,
                evidence={index for value in values for index in value.evidence_message_indices},
                reasoning=" ".join(
                    dict.fromkeys(value.reasoning for value in values if value.reasoning)
                ),
                correct_behavior=next(
                    (value.correct_behavior for value in values if value.correct_behavior), None
                ),
                sources={source for value in values for source in value.sources},
                confidence=max(value.confidence for value in values),
                review_tags=(tag for value in values for tag in value.review_tags),
                excerpt=next(
                    (value.evidence_excerpt for value in values if value.evidence_excerpt), ""
                ),
            )
        )
    return merged


def detect_failures(results: dict[str, Any]) -> list[FailureEvent]:
    """Normalize all available failure evidence for every simulation."""

    events: list[FailureEvent] = []
    for simulation in results.get("simulations") or []:
        if not isinstance(simulation, dict):
            continue
        events.extend(review_failure_events(simulation))
        events.extend(structural_failure_events(simulation))
        events.extend(outcome_failure_events(simulation))
    return _merge(events)


def summarize_failures(events: Sequence[FailureEvent]) -> dict[str, Any]:
    return {
        "schema_version": FAILURE_EVENT_SCHEMA,
        "detector_version": DETECTOR_VERSION,
        "event_count": len(events),
        "simulation_count": len({event.simulation_id for event in events}),
        "steerable_event_count": sum(event.steerable for event in events),
        "actor_counts": dict(sorted(Counter(event.actor for event in events).items())),
        "category_counts": dict(sorted(Counter(event.category for event in events).items())),
        "source_counts": dict(
            sorted(Counter(source for event in events for source in event.sources).items())
        ),
    }


def _agent_turns(simulation: dict[str, Any]) -> list[int]:
    return sorted(
        {
            value
            for message in simulation.get("messages") or []
            if message.get("role") == "assistant" and (value := _turn(message)) is not None
        }
    )


def build_replay_plan(
    results: dict[str, Any],
    events: Sequence[FailureEvent],
    *,
    seed: int = 42,
    minimum_confidence: float = 0.5,
) -> dict[str, Any]:
    """Build oracle and matched controls from automatically detected labels."""

    simulations = {
        str(simulation.get("id", "")): simulation
        for simulation in results.get("simulations") or []
        if isinstance(simulation, dict)
    }
    grouped: dict[str, list[FailureEvent]] = defaultdict(list)
    for event in events:
        if event.steerable and event.confidence >= minimum_confidence:
            grouped[event.simulation_id].append(event)

    entries: list[dict[str, Any]] = []
    for simulation_id in sorted(grouped):
        simulation = simulations.get(simulation_id)
        if simulation is None:
            continue
        by_turn: dict[int, list[FailureEvent]] = defaultdict(list)
        for event in grouped[simulation_id]:
            assert event.first_bad_turn is not None
            by_turn[event.first_bad_turn].append(event)
        target_turns = sorted(by_turn)
        all_turns = _agent_turns(simulation)
        candidates = [turn for turn in all_turns if turn not in by_turn]
        rng = random.Random(_stable_id(seed, simulation_id))
        if len(candidates) >= len(target_turns):
            random_turns = sorted(rng.sample(candidates, len(target_turns)))
        else:
            # Dense failure trajectories may have too few clean turns. Sampling
            # from every agent turn keeps intervention count exactly matched;
            # overlap is reported explicitly rather than silently shortening the
            # random control dose.
            random_turns = sorted(rng.sample(all_turns, len(target_turns)))
        random_overlap = sorted(set(random_turns).intersection(target_turns))
        entries.append(
            {
                "baseline_simulation_id": simulation_id,
                "task_id": str(simulation.get("task_id", "")),
                "trial": int(simulation.get("trial", 0) or 0),
                "oracle_interventions": [
                    {
                        "turn_idx": turn_idx,
                        "event_ids": [event.event_id for event in by_turn[turn_idx]],
                        "categories": sorted({event.category for event in by_turn[turn_idx]}),
                    }
                    for turn_idx in target_turns
                ],
                "count_matched_random_turns": random_turns,
                "random_overlap_with_oracle": random_overlap,
                "random_intervention_count_matched": len(random_turns) == len(target_turns),
                "conditions": [
                    "no_steer",
                    "oracle_gate",
                    "learned_gate",
                    "count_matched_random_gate",
                    "negative_direction",
                    "wrong_category",
                ],
            }
        )

    identity = {
        "timestamp": results.get("timestamp"),
        "git_commit": (results.get("info") or {}).get("git_commit"),
        "simulation_ids": sorted(simulations),
    }
    return {
        "schema_version": FAILURE_REPLAY_SCHEMA,
        "detector_version": DETECTOR_VERSION,
        "source_fingerprint": hashlib.sha256(_canonical_json(identity).encode()).hexdigest(),
        "seed": seed,
        "minimum_confidence": minimum_confidence,
        "notes": {
            "oracle_gate": "Post-hoc upper bound; never report as an online detector result.",
            "learned_gate": "Train and validate on disjoint task/conversation IDs.",
            "reference_actions": "Not treated as the unique valid action sequence.",
            "user_errors": "Audited but excluded from agent steering targets.",
        },
        "simulations": entries,
    }


def load_results(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("simulations"), list):
        raise ValueError("expected a TauBench results object with a simulations list")
    return value


def merge_results(results: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Combine disjoint Tau2 result shards without dropping review annotations."""
    shards = list(results)
    if len(shards) < 2:
        raise ValueError("merging requires at least two Tau2 result shards")
    simulations: list[dict[str, Any]] = []
    seen: set[str] = set()
    source_fingerprints: list[str] = []
    for shard in shards:
        if not isinstance(shard, dict) or not isinstance(shard.get("simulations"), list):
            raise ValueError("every merged shard must be a Tau2 results object")
        source_fingerprints.append(
            hashlib.sha256(_canonical_json(shard.get("simulations")).encode()).hexdigest()
        )
        for simulation in shard["simulations"]:
            if not isinstance(simulation, dict):
                raise ValueError("Tau2 simulations must be objects")
            simulation_id = str(simulation.get("id", ""))
            if not simulation_id or simulation_id in seen:
                raise ValueError("merged Tau2 simulations require unique non-empty IDs")
            seen.add(simulation_id)
            simulations.append(simulation)
    merged = dict(shards[0])
    merged["simulations"] = simulations
    info = dict(merged.get("info") or {})
    info["jlens_merged_result_shards"] = len(shards)
    info["jlens_source_fingerprints"] = source_fingerprints
    merged["info"] = info
    return merged


def write_events(path: str | Path, events: Sequence[FailureEvent]) -> Path:
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        for event in events:
            handle.write(_canonical_json(event.to_dict()) + "\n")
    return output


def read_events(path: str | Path) -> list[FailureEvent]:
    events: list[FailureEvent] = []
    for line_number, line in enumerate(
        Path(path).expanduser().resolve().read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        value = json.loads(line)
        if value.pop("schema_version", None) != FAILURE_EVENT_SCHEMA:
            raise ValueError(f"unsupported failure event schema on line {line_number}")
        value.pop("steerable", None)
        for key in ("evidence_message_indices", "sources", "review_tags"):
            value[key] = tuple(value.get(key) or ())
        events.append(FailureEvent(**value))
    return events
