"""Command-line entry point for Tool-Schema Doctor.

Subcommands: inspect, compatibility, lint, report, eval.
Exit codes: 0 = ran OK (findings are normal output); 2 = bad usage/input; 1 = internal error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import providers
from .loader import InputError, load_tools
from .model import to_jsonable
from .compat import run_compatibility, summarize
from .lint import RULES, run_lint, lint_summary
from .report import build_report, render_markdown
from . import selection_eval as sev

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_USAGE = 2


def _force_utf8_stdio() -> None:
    """Avoid UnicodeEncodeError when printing reports on a non-UTF-8 console
    (e.g. Windows cp1252): tool descriptions may contain arbitrary Unicode."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


def _emit(obj, out_path: str | None) -> None:
    text = json.dumps(to_jsonable(obj), indent=2, sort_keys=False, ensure_ascii=False)
    if out_path:
        Path(out_path).write_text(text, encoding="utf-8")
        print(f"wrote {out_path}", file=sys.stderr)
    else:
        print(text)


def cmd_inspect(args) -> int:
    records = load_tools(args.input)
    with_schema = sum(1 for r in records if r.has_schema)
    with_tags = sum(1 for r in records if r.has_tags)
    kw_counts: dict[str, int] = {}
    for r in records:
        if r.has_schema:
            for k in providers.keywords_present(r.input_parameters):
                kw_counts[k] = kw_counts.get(k, 0) + 1
    out = {
        "input": str(args.input),
        "source": records[0].source if records else None,
        "tools": len(records),
        "with_schema": with_schema,
        "with_tags": with_tags,
        "available_providers": providers.available_providers(),
        "schema_keyword_prevalence": dict(sorted(kw_counts.items(), key=lambda x: -x[1])),
    }
    _emit(out, args.output)
    return EXIT_OK


def cmd_compatibility(args) -> int:
    records = load_tools(args.input)
    provider_ids = None
    if args.providers:
        provider_ids = [p.strip() for p in args.providers.split(",") if p.strip()]
        unknown = [p for p in provider_ids if p not in providers.PROVIDER_IDS]
        if unknown:
            print(f"unknown provider(s): {unknown}; known: {providers.PROVIDER_IDS}",
                  file=sys.stderr)
            return EXIT_USAGE
    results = run_compatibility(records, provider_ids)
    out = {
        "input": str(args.input),
        "tools": len(records),
        "summary": summarize(results),
        "results": results if args.verbose else [r for r in results if r.status in ("error", "unavailable")],
    }
    _emit(out, args.output)
    return EXIT_OK


def cmd_lint(args) -> int:
    records = load_tools(args.input)
    rule_ids = None
    if args.rules:
        rule_ids = [r.strip() for r in args.rules.split(",") if r.strip()]
        unknown = [r for r in rule_ids if r not in RULES]
        if unknown:
            print(f"unknown rule(s): {unknown}; known: {list(RULES)}", file=sys.stderr)
            return EXIT_USAGE
    findings, skipped = run_lint(records, rule_ids)
    out = {
        "input": str(args.input),
        "source": records[0].source if records else None,
        "tools": len(records),
        "summary": lint_summary(findings),
        "skipped_rules": skipped,
        "findings": findings if args.verbose else findings[:200],
        "truncated": (not args.verbose) and len(findings) > 200,
    }
    _emit(out, args.output)
    return EXIT_OK


def cmd_report(args) -> int:
    records = load_tools(args.input)
    provider_ids = None
    if args.providers:
        provider_ids = [p.strip() for p in args.providers.split(",") if p.strip()]
        unknown = [p for p in provider_ids if p not in providers.PROVIDER_IDS]
        if unknown:
            print(f"unknown provider(s): {unknown}", file=sys.stderr)
            return EXIT_USAGE
    rule_ids = None
    if args.rules:
        rule_ids = [r.strip() for r in args.rules.split(",") if r.strip()]
    report = build_report(
        records, provider_ids, rule_ids,
        input_path=str(args.input),
        run_compat=not args.no_compat,
        run_lint_checks=not args.no_lint,
    )
    fmt = args.format
    if args.output:
        out = Path(args.output)
        out.mkdir(parents=True, exist_ok=True)
        if fmt in ("json", "both"):
            (out / "report.json").write_text(
                json.dumps(to_jsonable(report), indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"wrote {out / 'report.json'}", file=sys.stderr)
        if fmt in ("markdown", "both"):
            (out / "report.md").write_text(render_markdown(report), encoding="utf-8")
            print(f"wrote {out / 'report.md'}", file=sys.stderr)
    else:
        if fmt == "json":
            print(json.dumps(to_jsonable(report), indent=2, ensure_ascii=False))
        else:
            print(render_markdown(report))
    return EXIT_OK


DEFAULT_CORPUS = [
    "composio-upstream/ts/packages/cli/test/__mocks__/tools.json",
    "composio-upstream/docs/public/data/toolkits.json",
]


def cmd_eval(args) -> int:
    dataset = sev.load_dataset(args.dataset)
    corpus_paths = ([p.strip() for p in args.corpus.split(",") if p.strip()]
                    if args.corpus else DEFAULT_CORPUS)
    corpus = sev.build_corpus_map(corpus_paths)
    problems = sev.validate_dataset(dataset, corpus)

    if not args.live:
        out = {
            "mode": "offline-validation",
            "dataset": dataset.get("meta", {}).get("name"),
            "tasks": len(dataset["tasks"]),
            "integrity_problems": problems,
            "ok": not problems,
            "note": "pass --live (needs GROQ_API_KEY) to run the LLM selection.",
        }
        _emit(out, args.output)
        return EXIT_OK if not problems else EXIT_USAGE

    if problems:
        print(f"dataset integrity problems, refusing live run: {problems}", file=sys.stderr)
        return EXIT_USAGE
    if not os.environ.get("GROQ_API_KEY"):
        print("GROQ_API_KEY not set; required for --live", file=sys.stderr)
        return EXIT_USAGE

    report = sev.run_eval(dataset, corpus, model=args.model)
    if args.output:
        outp = Path(args.output)
        if outp.suffix != ".json":
            outp.mkdir(parents=True, exist_ok=True)
            outp = outp / "eval_report.json"
        outp.write_text(json.dumps(to_jsonable(report), indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {outp}", file=sys.stderr)
    # always print metrics to stdout
    print(json.dumps({"meta": report.meta, "metrics": report.metrics}, indent=2, ensure_ascii=False))
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tool-schema-doctor",
                                description="Offline QA for Composio tool schemas.")
    sub = p.add_subparsers(dest="command", required=True)

    pi = sub.add_parser("inspect", help="load a fixture and summarize it (no adapters)")
    pi.add_argument("--input", required=True)
    pi.add_argument("-o", "--output", default=None)
    pi.set_defaults(func=cmd_inspect)

    pc = sub.add_parser("compatibility", help="run tools through provider adapters")
    pc.add_argument("--input", required=True)
    pc.add_argument("--providers", default=None,
                    help=f"comma-separated subset of {providers.PROVIDER_IDS}")
    pc.add_argument("--verbose", action="store_true",
                    help="include ok/transformed results, not just errors")
    pc.add_argument("-o", "--output", default=None)
    pc.set_defaults(func=cmd_compatibility)

    pl = sub.add_parser("lint", help="deterministic metadata lint")
    pl.add_argument("--input", required=True)
    pl.add_argument("--rules", default=None,
                    help=f"comma-separated subset of {list(RULES)}")
    pl.add_argument("--verbose", action="store_true", help="emit all findings (no truncation)")
    pl.add_argument("-o", "--output", default=None)
    pl.set_defaults(func=cmd_lint)

    pr = sub.add_parser("report", help="combined compatibility + lint report (JSON/Markdown)")
    pr.add_argument("--input", required=True)
    pr.add_argument("--providers", default=None)
    pr.add_argument("--rules", default=None)
    pr.add_argument("--format", choices=["json", "markdown", "both"], default="both")
    pr.add_argument("--no-compat", action="store_true", help="skip provider compatibility")
    pr.add_argument("--no-lint", action="store_true", help="skip metadata lint")
    pr.add_argument("-o", "--output", default=None, help="output DIRECTORY for report.json/report.md")
    pr.set_defaults(func=cmd_report)

    pe = sub.add_parser("eval", help="LLM tool-selection eval (offline validation; --live calls Groq)")
    pe.add_argument("--dataset", default=None, help="path to eval dataset JSON (default: bundled)")
    pe.add_argument("--corpus", default=None,
                    help="comma-separated fixture paths to resolve descriptions (default: upstream mock+catalog)")
    pe.add_argument("--model", default=sev.DEFAULT_MODEL, help=f"Groq model id (default {sev.DEFAULT_MODEL})")
    pe.add_argument("--live", action="store_true", help="actually call Groq (needs GROQ_API_KEY)")
    pe.add_argument("-o", "--output", default=None)
    pe.set_defaults(func=cmd_eval)

    return p


def main(argv=None) -> int:
    _force_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except InputError as e:
        print(f"input error: {e}", file=sys.stderr)
        return EXIT_USAGE
    except Exception as e:  # noqa: BLE001
        print(f"internal error: {type(e).__name__}: {e}", file=sys.stderr)
        return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
