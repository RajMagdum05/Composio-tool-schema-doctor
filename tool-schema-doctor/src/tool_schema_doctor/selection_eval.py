"""LLM tool-selection evaluation (optional, opt-in, network-gated).

This evaluator ONLY selects a tool from a candidate set. It never executes any
Composio tool or performs real actions. Live runs require GROQ_API_KEY in the
environment; without --live it validates the dataset offline (no network).

Candidate tool descriptions are resolved from the real upstream fixtures at
runtime, so the dataset stays grounded in genuine metadata.
"""

from __future__ import annotations

import collections
import dataclasses
import datetime as _dt
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .loader import load_tools

DEFAULT_MODEL = "openai/gpt-oss-20b"
PROMPT_VERSION = "v1"

_SYSTEM = (
    "You are a precise tool-selection assistant. Given a user request and a list "
    "of candidate tools (each with a slug and a description), choose the SINGLE "
    "best tool to fulfil the request. You only select; you never call tools. "
    "Respond ONLY with a JSON object: {\"chosen_slug\": \"<one candidate slug>\", "
    "\"reasoning\": \"<one short sentence>\"}. chosen_slug MUST be exactly one of "
    "the candidate slugs."
)


@dataclass
class TaskResult:
    id: str
    expected: str
    chosen: Optional[str]
    correct: bool
    valid: bool  # chosen was one of the candidate slugs
    category: str
    difficulty: str
    reasoning: str = ""
    error: Optional[str] = None


@dataclass
class EvalReport:
    meta: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
    results: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Dataset + corpus
# ---------------------------------------------------------------------------

def default_dataset_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "eval_dataset.json"


def load_dataset(path: str | Path | None = None) -> dict:
    p = Path(path) if path else default_dataset_path()
    return json.loads(Path(p).read_text(encoding="utf-8"))


def build_corpus_map(corpus_paths: list[str]) -> dict[str, dict]:
    """slug -> {name, description} merged across the given fixtures."""
    out: dict[str, dict] = {}
    for cp in corpus_paths:
        for r in load_tools(cp):
            out.setdefault(r.slug, {"name": r.name, "description": r.description})
    return out


def validate_dataset(dataset: dict, corpus: dict[str, dict]) -> list[str]:
    """Return a list of integrity problems (empty == clean)."""
    problems = []
    seen_ids = set()
    for task in dataset["tasks"]:
        tid = task["id"]
        if tid in seen_ids:
            problems.append(f"{tid}: duplicate id")
        seen_ids.add(tid)
        cands = task["candidates"]
        if task["expected"] not in cands:
            problems.append(f"{tid}: expected '{task['expected']}' not in candidates")
        if len(cands) < 2:
            problems.append(f"{tid}: needs >= 2 candidates")
        for s in cands:
            if s not in corpus:
                problems.append(f"{tid}: candidate '{s}' not found in corpus")
    return problems


# ---------------------------------------------------------------------------
# Prompt + parsing
# ---------------------------------------------------------------------------

def build_messages(task: dict, corpus: dict[str, dict]) -> list[dict]:
    lines = [f"User request: {task['user_request']}", "", "Candidate tools:"]
    for s in task["candidates"]:
        desc = (corpus.get(s, {}).get("description") or "").strip()
        lines.append(f"- slug: {s}\n  description: {desc}")
    lines.append("")
    lines.append("Return JSON with chosen_slug (one of the slugs above) and reasoning.")
    return [{"role": "system", "content": _SYSTEM},
            {"role": "user", "content": "\n".join(lines)}]


def parse_selection(raw: str, candidates: list[str]) -> tuple[Optional[str], str]:
    """Parse the model's JSON. Returns (chosen_slug|None, reasoning)."""
    try:
        obj = json.loads(raw)
    except Exception:
        return None, ""
    if not isinstance(obj, dict):
        return None, ""
    chosen = obj.get("chosen_slug")
    reasoning = str(obj.get("reasoning", ""))[:300]
    if chosen not in candidates:
        # tolerate case/whitespace drift
        norm = {c.lower(): c for c in candidates}
        chosen = norm.get(str(chosen).strip().lower())
    return chosen, reasoning


# ---------------------------------------------------------------------------
# Selection (live Groq call) — pluggable `selector` for offline testing
# ---------------------------------------------------------------------------

def groq_selector(model: str):
    """Return a selector(messages)->raw_json_string backed by Groq. Network."""
    from groq import Groq  # optional dep

    client = Groq(api_key=os.environ["GROQ_API_KEY"])

    def _select(messages):
        resp = client.chat.completions.create(
            model=model, messages=messages, temperature=0,
            response_format={"type": "json_object"}, max_tokens=300,
        )
        return resp.choices[0].message.content

    return _select


def run_eval(dataset: dict, corpus: dict[str, dict], *, selector=None,
             model: str = DEFAULT_MODEL) -> EvalReport:
    """Run the eval. If selector is None, builds a live Groq selector.

    `selector` is a callable(messages)->raw_json_string; injecting one keeps the
    metrics logic testable offline without network.
    """
    if selector is None:
        selector = groq_selector(model)

    results: list[TaskResult] = []
    for task in dataset["tasks"]:
        cands = task["candidates"]
        messages = build_messages(task, corpus)
        chosen, reasoning, err = None, "", None
        try:
            raw = selector(messages)
            chosen, reasoning = parse_selection(raw, cands)
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {str(e)[:200]}"
        results.append(TaskResult(
            id=task["id"], expected=task["expected"], chosen=chosen,
            correct=(chosen == task["expected"]),
            valid=(chosen in cands),
            category=task.get("ambiguity_category", "?"),
            difficulty=task.get("difficulty", "?"),
            reasoning=reasoning, error=err,
        ))

    metrics = compute_metrics(results)
    meta = {
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "model": model, "prompt_version": PROMPT_VERSION,
        "dataset": dataset.get("meta", {}).get("name"),
        "selection_only": True,
        "disclosure": "Results depend on the model and prompt; a different model or prompt will score differently.",
    }
    return EvalReport(meta=meta, metrics=metrics,
                      results=[dataclasses.asdict(r) for r in results])


def compute_metrics(results: list[TaskResult]) -> dict:
    n = len(results)
    correct = sum(1 for r in results if r.correct)
    invalid = sum(1 for r in results if not r.valid)
    errored = sum(1 for r in results if r.error)

    def bucket(key):
        agg = collections.defaultdict(lambda: [0, 0])
        for r in results:
            b = agg[getattr(r, key)]
            b[1] += 1
            if r.correct:
                b[0] += 1
        return {k: {"correct": v[0], "total": v[1],
                    "accuracy": round(v[0] / v[1], 3) if v[1] else 0.0}
                for k, v in sorted(agg.items())}

    return {
        "total": n,
        "correct": correct,
        "accuracy": round(correct / n, 3) if n else 0.0,
        "incorrect_selection_rate": round((n - correct) / n, 3) if n else 0.0,
        "invalid_slug_count": invalid,
        "error_count": errored,
        "by_category": bucket("category"),
        "by_difficulty": bucket("difficulty"),
    }
