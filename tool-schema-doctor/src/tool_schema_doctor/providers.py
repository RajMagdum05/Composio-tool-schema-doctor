"""Provider registry: calls the REAL Composio adapters offline.

Every conversion function here imports and invokes the genuine provider class
(or SDK utility). No adapter logic is reimplemented. This mirrors the validated
pattern in investigation/repro_providers.py, packaged as a library.

- offline() blocks the network for the duration of a run, then restores it
  (defense in depth; wrap_tool is pure). enforce_offline() is the permanent,
  opt-in variant.
- _never_execute() guarantees no tool is ever executed.
- Each provider is imported lazily; a missing SDK surfaces as `unavailable`.
"""

from __future__ import annotations

import contextlib
import json
import socket
import traceback
from typing import Any, Callable, Optional

# Ordered list of provider ids the checker knows about.
PROVIDER_IDS = [
    "openai",
    "openai_strict",
    "anthropic",
    "google_vertex",
    "gemini",
    "google_adk",
]

# Schema keywords whose presence/absence we track across a conversion.
TRACKED_KEYWORDS = (
    "examples", "file_uploadable", "enum", "anyOf", "oneOf", "$ref",
    "const", "title", "default", "format", "additionalProperties", "items",
)

_OFFLINE_ENFORCED = False
_OFFLINE_DEPTH = 0
_REAL_CONNECT = socket.socket.connect
_REAL_GETADDRINFO = socket.getaddrinfo


def _blocked(*_a, **_k):
    raise RuntimeError("network access is blocked: Tool-Schema Doctor runs offline")


@contextlib.contextmanager
def offline():
    """Block the network only for the duration of the block, then restore it.

    Scoped (and nesting-safe) so library callers in long-lived processes — a
    notebook, a server, the Streamlit dashboard — keep their own networking
    after a compatibility run.
    """
    global _OFFLINE_DEPTH
    if _OFFLINE_DEPTH == 0 and not _OFFLINE_ENFORCED:
        socket.socket.connect = _blocked  # type: ignore[assignment]
        socket.getaddrinfo = _blocked  # type: ignore[assignment]
    _OFFLINE_DEPTH += 1
    try:
        yield
    finally:
        _OFFLINE_DEPTH -= 1
        if _OFFLINE_DEPTH == 0 and not _OFFLINE_ENFORCED:
            socket.socket.connect = _REAL_CONNECT  # type: ignore[assignment]
            socket.getaddrinfo = _REAL_GETADDRINFO  # type: ignore[assignment]


def enforce_offline() -> None:
    """Block the network for the rest of the process (opt-in, permanent).

    Prefer the scoped `offline()` context manager; this exists for callers that
    explicitly want a process-wide guarantee. Idempotent.
    """
    global _OFFLINE_ENFORCED
    if _OFFLINE_ENFORCED:
        return
    socket.socket.connect = _blocked  # type: ignore[assignment]
    socket.getaddrinfo = _blocked  # type: ignore[assignment]
    _OFFLINE_ENFORCED = True


def _never_execute(*_a, **_k):
    raise AssertionError("tool execution attempted during schema conversion")


def _make_tool(slug: str, description: str, input_parameters: dict):
    """Build a composio Tool exactly as the upstream tests/repro do."""
    from composio.client.types import Tool  # lazy: composio is the one hard dep

    return Tool.model_construct(
        slug=slug,
        name=slug,
        description=description or f"Tool {slug}",
        input_parameters=input_parameters,
    )


# ---------------------------------------------------------------------------
# Conversion functions — each returns the provider-side parameter schema.
# ---------------------------------------------------------------------------

def _conv_openai(slug, description, params):
    from composio_openai import OpenAIProvider

    out = OpenAIProvider().wrap_tool(_make_tool(slug, description, params))
    return out["function"]["parameters"]


def _conv_openai_strict(slug, description, params):
    from composio.utils.strict_schema import to_strict_json_schema

    res = to_strict_json_schema(params)
    if getattr(res, "unsupported", None):
        # Same wording as the SDK's own fallback warning in
        # composio/core/provider/_openai_responses.py: "<path>: <keyword> (<detail>)".
        detail = "; ".join(
            f"{getattr(u, 'path', None) or '<root>'}: "
            f"{getattr(u, 'keyword', '?')} ({getattr(u, 'detail', '')})"
            for u in res.unsupported
        )
        raise ValueError("strict-unsupported: " + detail)
    return res.schema


def _conv_anthropic(slug, description, params):
    from composio_anthropic import AnthropicProvider

    return dict(AnthropicProvider().wrap_tool(_make_tool(slug, description, params)))["input_schema"]


def _conv_google_vertex(slug, description, params):
    from composio_google import GoogleProvider

    decl = GoogleProvider().wrap_tool(_make_tool(slug, description, params))
    return decl.to_dict().get("parameters")


def _conv_gemini(slug, description, params):
    from composio_gemini import GeminiProvider
    from google import genai
    from google.genai import types as gt

    func = GeminiProvider().wrap_tool(_make_tool(slug, description, params), _never_execute)
    decl = gt.FunctionDeclaration.from_callable(
        client=genai.Client(api_key="offline-test")._api_client, callable=func
    )
    return decl.parameters.model_dump(exclude_none=True, mode="json") if decl.parameters else None


def _conv_google_adk(slug, description, params):
    from composio_google_adk import GoogleAdkProvider

    wrapped = GoogleAdkProvider().wrap_tool(_make_tool(slug, description, params), execute_tool=_never_execute)
    decl = wrapped._get_declaration()
    if getattr(decl, "parameters_json_schema", None) is not None:
        return decl.parameters_json_schema
    return decl.parameters.model_dump(exclude_none=True, mode="json") if decl.parameters else None


_CONVERTERS: dict[str, Callable[[str, str, dict], Any]] = {
    "openai": _conv_openai,
    "openai_strict": _conv_openai_strict,
    "anthropic": _conv_anthropic,
    "google_vertex": _conv_google_vertex,
    "gemini": _conv_gemini,
    "google_adk": _conv_google_adk,
}

# Import probe per provider: (module names that must import for it to be usable)
_PROBE: dict[str, list[str]] = {
    "openai": ["composio_openai"],
    "openai_strict": ["composio"],
    "anthropic": ["composio_anthropic"],
    "google_vertex": ["composio_google"],
    "gemini": ["composio_gemini", "google.genai"],
    "google_adk": ["composio_google_adk"],
}


def available_providers() -> dict[str, bool]:
    """Return {provider_id: importable?} without executing the heavy SDKs.

    Uses importlib.util.find_spec so probing availability does not import
    (and pay the cost of) Vertex / google-genai / ADK etc.
    """
    import importlib.util

    out: dict[str, bool] = {}
    for pid, mods in _PROBE.items():
        ok = True
        for m in mods:
            try:
                if importlib.util.find_spec(m) is None:
                    ok = False
                    break
            except Exception:
                ok = False
                break
        out[pid] = ok
    return out


def convert(provider_id: str, slug: str, description: str, params: dict) -> Any:
    """Run one tool through one provider. Raises on adapter failure."""
    return _CONVERTERS[provider_id](slug, description, params)


# ---------------------------------------------------------------------------
# Helpers for diffing and locating schema keywords.
# ---------------------------------------------------------------------------

def keywords_present(obj: Any, found: Optional[set] = None) -> set:
    found = set() if found is None else found
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in TRACKED_KEYWORDS:
                found.add(k)
            keywords_present(v, found)
    elif isinstance(obj, list):
        for v in obj:
            keywords_present(v, found)
    return found


def first_path(params: dict, keyword: str, *, nested_only: bool = False) -> Optional[str]:
    """Return the JSON-pointer-ish path of the first occurrence of `keyword`.

    If nested_only, skip occurrences directly under the top-level `properties`
    (depth 1), matching what the Vertex adapter strips.
    """
    def _is_top_level_property(parent_path: str) -> bool:
        # The keyword sits directly on a property schema that is a direct child
        # of the root `properties` object, i.e. parent path == "/properties/<name>"
        # (or on the root schema itself). Those are what the Vertex adapter strips.
        segs = [s for s in parent_path.split("/") if s]
        if not segs:
            return True
        return len(segs) == 2 and segs[0] == "properties"

    def walk(o: Any, path: str, depth: int) -> Optional[str]:
        if isinstance(o, dict):
            for k, v in o.items():
                hit_path = f"{path}/{k}"
                if k == keyword:
                    if not (nested_only and _is_top_level_property(path)):
                        return hit_path
                r = walk(v, hit_path, depth + 1)
                if r:
                    return r
        elif isinstance(o, list):
            for i, v in enumerate(o):
                r = walk(v, f"{path}/{i}", depth + 1)
                if r:
                    return r
        return None

    return walk(params, "", 0)


def last_frame(exc: BaseException) -> Optional[str]:
    tb = traceback.extract_tb(exc.__traceback__)
    if not tb:
        return None
    fn = tb[-1].filename
    return fn.split("site-packages")[-1] if "site-packages" in fn else fn


def jsonsafe(obj: Any) -> Any:
    return json.loads(json.dumps(obj, default=str))
