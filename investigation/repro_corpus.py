"""Milestone 0: run every tool in the repo's offline mock corpus
(ts/packages/cli/test/__mocks__/tools.json, 930 tools) through each provider
adapter and record failures. Offline: network blocked, tools never executed.

Usage: REPRO_PROVIDERS=openai,gemini <venv>/python -I repro_corpus.py <repo_root>
"""

import collections
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import repro_providers as rp  # noqa: E402  (also blocks the network)

root = Path(sys.argv[1])
mock = json.loads((root / "ts/packages/cli/test/__mocks__/tools.json").read_text(encoding="utf-8"))

only = [p for p in os.environ.get("REPRO_PROVIDERS", "").split(",") if p]
providers = {k: v for k, v in rp.PROVIDERS.items() if not only or any(k.startswith(o) for o in only)}

summary = {}
for pname, fn in providers.items():
    failures = []
    dropped = collections.Counter()
    for t in mock:
        tool = rp.Tool.model_construct(
            slug=t["slug"], description=t["description"], input_parameters=t["input_parameters"]
        )
        try:
            out = fn(tool)
            for k in rp.keywords_present(t["input_parameters"]) - rp.keywords_present(out):
                dropped[k] += 1
        except Exception as e:  # noqa: BLE001
            failures.append({"slug": t["slug"], "error_type": type(e).__name__, "error": str(e)[:300]})
    summary[pname] = {
        "tools": len(mock),
        "failures": len(failures),
        "failure_types": collections.Counter(f["error_type"] for f in failures).most_common(),
        "failure_samples": failures[:10],
        "tools_losing_keyword": dict(dropped.most_common()),
    }
    print(f"{pname}: {len(failures)} failures", file=sys.stderr, flush=True)

json.dump(summary, sys.stdout, indent=1, default=str)
