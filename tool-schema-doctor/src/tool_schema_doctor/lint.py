"""Deterministic metadata linter.

Each rule has a stable id, a severity, a rationale, and emits findings with
evidence + remediation. Rules declare what data they need (tags vs. description)
and are skipped with a reason when the input lacks it — so a names-only catalog
never produces bogus "missing hint" findings. Counts always come from the input
you pass; the caller is responsible for not mixing fixtures (see decision D3).
"""

from __future__ import annotations

import collections
import re
from typing import Callable, Iterable, Optional

from .model import (
    LintFinding, ToolRecord,
    SEV_ERROR, SEV_WARNING, SEV_INFO,
)

# Action hints (MCP-style), from composio tool_router.ToolRouterTag.
ACTION_HINTS = {"readOnlyHint", "createHint", "updateHint", "destructiveHint"}
ALL_HINTS = ACTION_HINTS | {"idempotentHint", "openWorldHint"}

DESTRUCTIVE_VERBS = re.compile(
    r"(^|_)(DELETE|REMOVE|DESTROY|PURGE|ERASE|REVOKE|DROP|TRUNCATE|CANCEL|DISABLE|UNSUBSCRIBE|BAN|KICK)(_|$)"
)
# Known false-positive patterns for the destructive-verb heuristic (see validation §4.2).
DESTRUCTIVE_ALLOWLIST = re.compile(r"(DOWNLOAD|REMOVE_TOKEN|REMOVE_A_TOKEN)")

DESC_TOO_LONG = 1024  # defensible threshold; catalog p99 = 943 (validation §4.6)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


# ---------------------------------------------------------------------------
# Individual rules. Each returns (findings, skipped_reason|None).
# ---------------------------------------------------------------------------

def rule_missing_action_hint(records: list[ToolRecord]):
    rid, sev = "missing-action-hint", SEV_WARNING
    if not any(r.has_tags for r in records):
        return [], "no tags in input (names-only catalog): hint rules not applicable"
    findings = []
    for r in records:
        # A tag-less tool in a tagged corpus still lacks an action hint — flag it.
        if not (set(r.tags) & ACTION_HINTS):
            findings.append(LintFinding(
                rid, sev, r.slug, toolkit=r.toolkit,
                message="tool has no action hint (readOnly/create/update/destructive)",
                evidence=f"tags={sorted(set(r.tags) & ALL_HINTS) or 'none of the hint tags'}",
                remediation="add the hint matching the tool's effect, e.g. createHint for a create action",
            ))
    return findings, None


def rule_destructive_verb_without_hint(records: list[ToolRecord]):
    rid, sev = "destructive-verb-without-destructive-hint", SEV_INFO
    if not any(r.has_tags for r in records):
        return [], "no tags in input: cannot check destructiveHint"
    findings = []
    for r in records:
        if DESTRUCTIVE_ALLOWLIST.search(r.slug):
            continue
        if DESTRUCTIVE_VERBS.search(r.slug) and "destructiveHint" not in r.tags:
            findings.append(LintFinding(
                rid, sev, r.slug, toolkit=r.toolkit,
                message="slug contains a destructive verb but the tool is not tagged destructiveHint",
                evidence=f"slug matches {DESTRUCTIVE_VERBS.pattern}",
                remediation="verify the effect; if it destroys/removes data, add destructiveHint (heuristic — review before acting)",
            ))
    return findings, None


def rule_duplicate_display_name_in_toolkit(records: list[ToolRecord]):
    rid, sev = "duplicate-display-name-in-toolkit", SEV_INFO
    # group by (toolkit, normalized name)
    groups: dict[tuple, list[ToolRecord]] = collections.defaultdict(list)
    for r in records:
        if not r.name:
            continue
        groups[(r.toolkit, _norm(r.name))].append(r)
    findings = []
    for (tk, nm), members in groups.items():
        if len(members) > 1:
            slugs = sorted(m.slug for m in members)
            for m in members:
                siblings = [s for s in slugs if s != m.slug]
                findings.append(LintFinding(
                    rid, sev, m.slug, toolkit=tk,
                    message=f"display name shared by {len(members)} tools in this toolkit (likely aliases/legacy)",
                    evidence=f"name={m.name!r}; siblings={siblings}",
                    remediation="not a slug collision; disambiguate display names or mark legacy aliases",
                ))
    return findings, None


def rule_description_repeats_name(records: list[ToolRecord]):
    rid, sev = "description-repeats-name", SEV_WARNING
    findings = []
    for r in records:
        if not r.description:
            continue
        nd = _norm(r.description)
        if nd and nd in (_norm(r.name), _norm(r.slug.replace("_", " "))):
            findings.append(LintFinding(
                rid, sev, r.slug, toolkit=r.toolkit,
                message="description just repeats the name/slug without explaining what the tool does",
                evidence=f"description={r.description[:80]!r}",
                remediation="describe inputs, effect, and when to use it",
            ))
    return findings, None


def rule_description_empty(records: list[ToolRecord]):
    rid, sev = "description-empty", SEV_WARNING
    findings = [
        LintFinding(rid, sev, r.slug, toolkit=r.toolkit,
                    message="empty description",
                    remediation="add a one-line description of the tool's effect")
        for r in records if not (r.description or "").strip()
    ]
    return findings, None


def rule_description_too_long(records: list[ToolRecord], threshold: int = DESC_TOO_LONG):
    rid, sev = "description-too-long", SEV_INFO
    findings = [
        LintFinding(rid, sev, r.slug, toolkit=r.toolkit,
                    message=f"description is {len(r.description)} chars (> {threshold})",
                    evidence=f"first 60: {r.description[:60]!r}",
                    remediation="trim to the essential behavior; move examples into schema or docs")
        for r in records if len(r.description or "") > threshold
    ]
    return findings, None


RULES: dict[str, Callable] = {
    "missing-action-hint": rule_missing_action_hint,
    "destructive-verb-without-destructive-hint": rule_destructive_verb_without_hint,
    "duplicate-display-name-in-toolkit": rule_duplicate_display_name_in_toolkit,
    "description-repeats-name": rule_description_repeats_name,
    "description-empty": rule_description_empty,
    "description-too-long": rule_description_too_long,
}


def run_lint(records: Iterable[ToolRecord], rule_ids: Optional[list[str]] = None):
    """Run the selected rules. Returns (findings, skipped{rule_id: reason})."""
    records = list(records)
    rule_ids = rule_ids or list(RULES)
    findings: list[LintFinding] = []
    skipped: dict[str, str] = {}
    for rid in rule_ids:
        fn = RULES.get(rid)
        if fn is None:
            skipped[rid] = "unknown rule"
            continue
        fs, reason = fn(records)
        if reason:
            skipped[rid] = reason
        findings.extend(fs)
    findings.sort(key=lambda f: (f.severity != SEV_ERROR, f.severity != SEV_WARNING, f.rule_id, f.slug))
    return findings, skipped


def lint_summary(findings: list[LintFinding]) -> dict:
    by_rule = collections.Counter(f.rule_id for f in findings)
    by_sev = collections.Counter(f.severity for f in findings)
    return {"total": len(findings), "by_rule": dict(by_rule), "by_severity": dict(by_sev)}
