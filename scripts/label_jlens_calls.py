"""Label every replayed tau2 call in a J-lens export against the task's gold actions.

A call is the assistant turn stored in ``<export>/<call_dir>/meta.json``
(segment "current assistant response").  Each emitted tool call is compared
with the gold ``evaluation_criteria.actions`` of its task:

* ``correct``        name and arguments equal one gold action
* ``wrong_args``     a gold action has the same name, none has the same arguments
* ``unexpected``     a state-changing tool that no gold action uses
* ``read_extra``     a read-only lookup that is not a gold action (harmless)

Usage:
    python scripts/label_jlens_calls.py <export_dir> <tasks.json> --output calls.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

READ_PREFIXES = ("get_", "find_", "list_", "calculate", "think", "search")
CALL_RE = re.compile(r"<tool_call>\s*<function=([^>\n]+)>(.*?)</function>\s*</tool_call>", re.S)
PARAM_RE = re.compile(r"<parameter=([^>\n]+)>\n?(.*?)\n?</parameter>", re.S)


def parse_tool_calls(text: str) -> list[dict[str, Any]]:
    calls = []
    for name, body in CALL_RE.findall(text):
        arguments: dict[str, Any] = {}
        for key, raw in PARAM_RE.findall(body):
            value = raw.strip()
            try:
                arguments[key.strip()] = json.loads(value)
            except json.JSONDecodeError:
                arguments[key.strip()] = value
        calls.append({"name": name.strip(), "arguments": arguments})
    return calls


def _normal(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _normal(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [_normal(v) for v in value]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return value


def label_call(call: dict[str, Any], gold: list[dict[str, Any]]) -> tuple[str, dict[str, Any] | None]:
    same_name = [action for action in gold if action["name"] == call["name"]]
    for action in same_name:
        if _normal(action.get("arguments") or {}) == _normal(call["arguments"]):
            return "correct", action
    if same_name:
        return "wrong_args", same_name[0]
    if call["name"].startswith(READ_PREFIXES):
        return "read_extra", None
    return "unexpected", None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("export_dir", type=Path)
    parser.add_argument("tasks", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    tasks = {str(task["id"]): task for task in json.loads(args.tasks.read_text(encoding="utf-8"))}
    rows = []
    for call_dir in sorted(path for path in args.export_dir.iterdir() if path.is_dir()):
        meta_path, analysis_path = call_dir / "meta.json", call_dir / "analysis.json"
        if not meta_path.is_file() or not analysis_path.is_file():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
        segment = next(s for s in meta["segments"] if s["kind"] == "assistant")
        response = "".join(meta["ctx_strs"][segment["start"] : segment["end"]])
        task = tasks.get(str(analysis["task_id"]))
        gold = (task or {}).get("evaluation_criteria", {}).get("actions") or []
        calls = parse_tool_calls(response)
        labels = [label_call(call, gold) for call in calls]
        rows.append(
            {
                "call_dir": call_dir.name,
                "task_id": str(analysis["task_id"]),
                "simulation_id": analysis["simulation_id"],
                "call_id": analysis["call_id"],
                "call_index": analysis["call_index"],
                "outcome": analysis["outcome"],
                "reward": analysis["reward"],
                "request_tokens": segment["start"],
                "response": response,
                "tool_calls": calls,
                "labels": [label for label, _ in labels],
                "gold_matches": [match for _, match in labels],
                "call_label": (
                    "no_tool_call" if not labels else
                    "wrong_args" if any(label == "wrong_args" for label, _ in labels) else
                    "unexpected" if any(label == "unexpected" for label, _ in labels) else
                    "correct" if any(label == "correct" for label, _ in labels) else
                    "read_extra"
                ),
            }
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"calls": len(rows), "labels": Counter(row["call_label"] for row in rows),
                      "by_outcome": Counter(f"{row['outcome']}/{row['call_label']}" for row in rows)},
                     indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
