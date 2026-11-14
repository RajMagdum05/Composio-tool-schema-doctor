"""Build and render the combined compatibility + lint report (JSON / Markdown)."""

from __future__ import annotations

import datetime as _dt
from typing import Optional

from .model import Report, ToolRecord, ERROR, UNAVAILABLE
from .compat import run_compatibility, summarize
from .lint import run_lint, lint_summary

FIXTURE_NOTES = {
    "mock": (
        "Input is the upstream CLI test mock (GitHub-heavy, ~930 tools). "
        "Counts are fixture statistics, NOT live-catalog rates."
    ),
    "catalog": (
        "Input is the docs catalog (names/descriptions only, no tags/schemas). "
        "Provider compatibility and hint lint do not apply here."
    ),
}


def build_report(
    records: list[ToolRecord],
    provider_ids: Optional[list[str]] = None,
    rule_ids: Optional[list[str]] = None,
    *,
    input_path: str = "",
    run_compat: bool = True,
    run_lint_checks: bool = True,
) -> Report:
    source = records[0].source if records else "unknown"
    with_schema = sum(1 for r in records if r.has_schema)
    with_tags = sum(1 for r in records if r.has_tags)

    compat_results = []
    lint_findings = []
    skipped: list[str] = []

    if run_compat:
        if with_schema == 0:
            skipped.append("compatibility: no input_parameters in this input (catalog)")
        else:
            compat_results = run_compatibility(records, provider_ids)

    lint_skipped: dict[str, str] = {}
    if run_lint_checks:
        lint_findings, lint_skipped = run_lint(records, rule_ids)
    for rid, reason in lint_skipped.items():
        skipped.append(f"lint:{rid}: {reason}")

    limitations = [
        "Offline only: results reflect the installed adapter versions; no live API/LLM calls.",
        "One failing tool does not stop the run; adapter errors are reported per tool.",
        FIXTURE_NOTES.get(source, "Input source is non-standard; verify provenance."),
    ]

    meta = {
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "input_path": input_path,
        "input_source": source,
        "counts": {"tools": len(records), "with_schema": with_schema, "with_tags": with_tags},
        "compatibility_summary": summarize(compat_results) if compat_results else {},
        "lint_summary": lint_summary(lint_findings) if lint_findings else {"total": 0},
    }
    return Report(meta=meta, compatibility=compat_results, lint=lint_findings,
                  skipped=skipped, limitations=limitations)


def render_markdown(report: Report) -> str:
    m = report.meta
    L: list[str] = []
    L.append("# Tool-Schema Doctor — Report")
    L.append("")
    L.append(f"- Generated: `{m.get('generated_at')}`")
    L.append(f"- Input: `{m.get('input_path')}` (source: **{m.get('input_source')}**)")
    c = m.get("counts", {})
    L.append(f"- Tools: **{c.get('tools')}** · with schema: {c.get('with_schema')} · with tags: {c.get('with_tags')}")
    L.append("")

    # Compatibility
    L.append("## Provider compatibility")
    csum = m.get("compatibility_summary") or {}
    if not csum:
        L.append("_No compatibility run (input has no schemas, or it was disabled)._")
        L.append("")
    else:
        statuses = ["ok", "transformed", "error", "unavailable", "skipped"]
        L.append("| Provider | " + " | ".join(statuses) + " |")
        L.append("|" + "---|" * (len(statuses) + 1))
        for prov in sorted(csum):
            row = csum[prov]
            L.append(f"| `{prov}` | " + " | ".join(str(row.get(s, 0)) for s in statuses) + " |")
        L.append("")
        errors = [r for r in report.compatibility if r.status == ERROR]
        if errors:
            L.append(f"### Failing conversions ({len(errors)})")
            L.append("| Tool | Provider | Error | Schema path |")
            L.append("|---|---|---|---|")
            for r in sorted(errors, key=lambda x: (x.provider, x.slug)):
                path = r.schema_path or ""
                msg = (r.error_type or "") + (f": {r.message}" if r.message else "")
                preview = msg if len(msg) <= 100 else msg[:100] + "…"   # full text is in report.json
                L.append(f"| `{r.slug}` | `{r.provider}` | {preview} | `{path}` |")
            L.append("")

    # Lint
    L.append("## Metadata lint")
    lsum = m.get("lint_summary") or {}
    L.append(f"Total findings: **{lsum.get('total', 0)}**")
    by_rule = lsum.get("by_rule") or {}
    if by_rule:
        L.append("")
        L.append("| Rule | Count |")
        L.append("|---|---|")
        for rid, cnt in sorted(by_rule.items(), key=lambda x: -x[1]):
            L.append(f"| `{rid}` | {cnt} |")
        L.append("")
        # a few examples per rule
        from collections import defaultdict
        ex = defaultdict(list)
        for f in report.lint:
            if len(ex[f.rule_id]) < 3:
                ex[f.rule_id].append(f)
        L.append("### Examples")
        for rid, items in ex.items():
            L.append(f"- **{rid}** ({items[0].severity}): " +
                     ", ".join(f"`{i.slug}`" for i in items))
        L.append("")

    if report.skipped:
        L.append("## Skipped checks")
        for s in report.skipped:
            L.append(f"- {s}")
        L.append("")

    L.append("## Limitations")
    for lim in report.limitations:
        L.append(f"- {lim}")
    L.append("")
    return "\n".join(L)
