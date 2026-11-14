"""Load tool fixtures into normalized ToolRecord objects.

Supports two shapes, auto-detected:
  1. Mock corpus: a JSON array of tool objects with full schemas + tags
     (e.g. ts/packages/cli/test/__mocks__/tools.json).
  2. Docs catalog: {"...": [{"slug": <toolkit>, "tools": [{slug,name,description}]}]}
     or a top-level list of toolkits (names/descriptions only, no schemas).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .model import ToolRecord


class InputError(Exception):
    """Raised when an input file cannot be parsed into tool records."""


def _toolkit_slug(tk: dict) -> str:
    return tk.get("slug") or tk.get("name") or "unknown"


def _record_from_mock(obj: dict) -> ToolRecord:
    return ToolRecord(
        slug=obj["slug"],
        name=obj.get("name", ""),
        description=obj.get("description", "") or "",
        tags=list(obj.get("tags") or []),
        input_parameters=obj.get("input_parameters"),
        toolkit=(obj["slug"].split("_")[0] if obj.get("slug") else None),
        source="mock",
    )


def _record_from_catalog(toolkit: str, obj: dict) -> ToolRecord:
    return ToolRecord(
        slug=obj["slug"],
        name=obj.get("name", ""),
        description=obj.get("description", "") or "",
        tags=list(obj.get("tags") or []),
        input_parameters=obj.get("input_parameters"),  # usually absent
        toolkit=toolkit,
        source="catalog",
    )


def _looks_like_toolkit(obj: Any) -> bool:
    return isinstance(obj, dict) and "tools" in obj and isinstance(obj.get("tools"), list)


def _looks_like_tool(obj: Any) -> bool:
    return isinstance(obj, dict) and "slug" in obj and "tools" not in obj


def parse_data(data: Any) -> list[ToolRecord]:
    """Convert already-parsed JSON into ToolRecords."""
    # Catalog as top-level list of toolkits
    if isinstance(data, list) and data and _looks_like_toolkit(data[0]):
        records: list[ToolRecord] = []
        for tk in data:
            tks = _toolkit_slug(tk)
            for t in tk.get("tools") or []:
                records.append(_record_from_catalog(tks, t))
        return records

    # Mock corpus: top-level list of tool objects
    if isinstance(data, list):
        if not data:
            return []
        if _looks_like_tool(data[0]):
            return [_record_from_mock(t) for t in data if _looks_like_tool(t)]
        raise InputError("JSON array does not contain tool objects (need a 'slug' field).")

    # Dict wrappers
    if isinstance(data, dict):
        # {"tools": [...]} direct list of tools
        if isinstance(data.get("tools"), list) and data["tools"] and _looks_like_tool(data["tools"][0]):
            return [_record_from_mock(t) for t in data["tools"] if _looks_like_tool(t)]
        # {"toolkits": [...]} or any dict whose values are toolkit lists
        for key in ("toolkits", "items", "data"):
            val = data.get(key)
            if isinstance(val, list) and val and _looks_like_toolkit(val[0]):
                return parse_data(val)
        raise InputError("Unrecognized object shape; expected a list of tools or toolkits.")

    raise InputError(f"Unsupported top-level JSON type: {type(data).__name__}")


def load_tools(path: str | Path) -> list[ToolRecord]:
    p = Path(path)
    if not p.exists():
        raise InputError(f"Input file not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise InputError(f"Invalid JSON in {p}: {e}") from e
    records = parse_data(data)
    if not records:
        raise InputError(f"No tools found in {p}")
    return records
