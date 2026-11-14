"""Milestone 0: quantify metadata claims against the two offline catalogs in
the Composio repo. Read-only, deterministic, stdlib only.

Usage: python -I repro_metadata.py <repo_root>
"""

import collections
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
DOCS = root / "docs/public/data/toolkits.json"
MOCK = root / "ts/packages/cli/test/__mocks__/tools.json"

# composio/core/models/tool_router.py: ToolRouterTag
HINTS = {"readOnlyHint", "createHint", "updateHint", "destructiveHint", "idempotentHint", "openWorldHint"}
ACTION_HINTS = {"readOnlyHint", "createHint", "updateHint", "destructiveHint"}
DESTRUCTIVE_VERBS = re.compile(r"(^|_)(DELETE|REMOVE|DESTROY|PURGE|ERASE|REVOKE|DROP|TRUNCATE|CANCEL|ARCHIVE|DISABLE|UNSUBSCRIBE|BAN|KICK|BLOCK)(_|$)")

out = {}

# ---------- mock corpus (has tags + schemas) ----------
mock = json.loads(MOCK.read_text(encoding="utf-8"))
n = len(mock)
no_hint = [t["slug"] for t in mock if not (set(t.get("tags") or []) & HINTS)]
no_action_hint = [t["slug"] for t in mock if not (set(t.get("tags") or []) & ACTION_HINTS)]
destructive_verb_no_destructive_hint = [
    t["slug"] for t in mock
    if DESTRUCTIVE_VERBS.search(t["slug"]) and "destructiveHint" not in (t.get("tags") or [])
]
readonly_and_destructive = [
    t["slug"] for t in mock if {"readOnlyHint", "destructiveHint"} <= set(t.get("tags") or [])
]
kw_counts = collections.Counter()


def walk(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if k in ("examples", "file_uploadable", "file_downloadable", "anyOf", "oneOf", "allOf", "$ref", "enum", "const", "default", "title", "additionalProperties"):
                kw_counts[k] += 1
            walk(v)
    elif isinstance(o, list):
        for v in o:
            walk(v)


tools_with_kw = collections.Counter()
for t in mock:
    before = dict(kw_counts)
    walk(t.get("input_parameters"))
    for k in kw_counts:
        if kw_counts[k] != before.get(k, 0):
            tools_with_kw[k] += 1

head_enum_tools = []
for t in mock:
    s = json.dumps(t.get("input_parameters"))
    if '"HEAD"' in s:
        head_enum_tools.append(t["slug"])

out["mock_corpus"] = {
    "path": str(MOCK.relative_to(root)),
    "tools": n,
    "slug_prefix_counts": collections.Counter(t["slug"].split("_")[0] for t in mock).most_common(),
    "tools_with_no_hint_tag": len(no_hint),
    "tools_with_no_action_hint(readOnly/create/update/destructive)": len(no_action_hint),
    "pct_no_action_hint": round(100 * len(no_action_hint) / n, 1),
    "no_action_hint_sample": no_action_hint[:10],
    "destructive_verb_slug_without_destructiveHint": len(destructive_verb_no_destructive_hint),
    "destructive_verb_sample": destructive_verb_no_destructive_hint[:15],
    "readOnly_and_destructive_both": readonly_and_destructive[:10],
    "tools_using_schema_keyword": dict(tools_with_kw.most_common()),
    "tools_with_HEAD_literal_in_schema": head_enum_tools[:20],
    "duplicate_slugs": [s for s, c in collections.Counter(t["slug"] for t in mock).items() if c > 1],
    "duplicate_names": {nm: c for nm, c in collections.Counter(t["name"] for t in mock).items() if c > 1},
}

# ---------- docs catalog (slug/name/description only) ----------
docs = json.loads(DOCS.read_text(encoding="utf-8"))
tools = [(tk["slug"], t) for tk in docs for t in (tk.get("tools") or [])]
slug_counts = collections.Counter(t["slug"] for _, t in tools)
within = collections.defaultdict(collections.Counter)
for tk, t in tools:
    within[tk][t["name"].strip().lower()] += 1
within_groups = [(tk, nm, c) for tk, cnt in within.items() for nm, c in cnt.items() if c > 1]
across = collections.defaultdict(set)
for tk, t in tools:
    across[t["name"].strip().lower()].add(tk)
across_groups = {nm: len(tks) for nm, tks in across.items() if len(tks) > 1}


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


desc_repeats_name = [
    t["slug"] for _, t in tools
    if t.get("description") and norm(t["description"]) in {norm(t["name"]), norm(t["slug"].replace("_", " "))}
]
empty_desc = [t["slug"] for _, t in tools if not (t.get("description") or "").strip()]
lens = sorted(len(t.get("description") or "") for _, t in tools)

out["docs_catalog"] = {
    "path": str(DOCS.relative_to(root)),
    "toolkits": len(docs),
    "tools": len(tools),
    "tool_fields": collections.Counter(k for _, t in tools for k in t).most_common(),
    "duplicate_slugs_global": sum(1 for c in slug_counts.values() if c > 1),
    "duplicate_slug_sample": [s for s, c in slug_counts.items() if c > 1][:10],
    "within_toolkit_duplicate_name_groups": len(within_groups),
    "within_toolkit_duplicate_sample": within_groups[:15],
    "cross_toolkit_duplicate_name_groups": len(across_groups),
    "cross_toolkit_sample": sorted(across_groups.items(), key=lambda x: -x[1])[:10],
    "description_equals_name_or_slug": len(desc_repeats_name),
    "description_equals_sample": desc_repeats_name[:10],
    "empty_descriptions": len(empty_desc),
    "description_length_p50_p95_p99_max": [lens[len(lens) // 2], lens[int(len(lens) * .95)], lens[int(len(lens) * .99)], lens[-1]],
    "descriptions_over_1024_chars": sum(1 for x in lens if x > 1024),
}

json.dump(out, sys.stdout, indent=1, default=str)
