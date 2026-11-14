"""Milestone 0 reproduction: push synthetic tool schemas through the real
Composio Python provider adapters, fully offline, and record what each one
accepts, rejects or transforms.

No API keys, no network (socket connect is blocked), no tool execution.
Run:  <venv>/python -I repro_providers.py  > repro_output.json
"""

import json
import socket
import sys
import traceback


def _no_network(*a, **k):
    raise RuntimeError("network blocked in repro")


socket.socket.connect = _no_network  # type: ignore[assignment]
socket.getaddrinfo = _no_network  # type: ignore[assignment]

from composio.client.types import Tool  # noqa: E402

CASES = {
    "baseline_simple": {
        "type": "object",
        "properties": {"owner": {"type": "string", "description": "Repo owner"}},
        "required": ["owner"],
    },
    "examples_top_level": {
        "type": "object",
        "properties": {"q": {"type": "string", "examples": ["foo", "bar"]}},
        "required": ["q"],
    },
    "examples_nested_object": {
        "type": "object",
        "properties": {
            "filter": {
                "type": "object",
                "properties": {"q": {"type": "string", "examples": ["foo"]}},
            }
        },
    },
    "examples_in_array_items": {
        "type": "object",
        "properties": {
            "tags": {"type": "array", "items": {"type": "string", "examples": ["x"]}}
        },
    },
    "file_uploadable_top_level": {
        "type": "object",
        "properties": {
            "attachment": {
                "type": "string",
                "format": "path",
                "file_uploadable": True,
                "description": "File to upload",
            }
        },
        "required": ["attachment"],
    },
    "file_uploadable_nested": {
        "type": "object",
        "properties": {
            "payload": {
                "type": "object",
                "properties": {
                    "file": {"type": "string", "file_uploadable": True},
                },
            }
        },
    },
    "enum_http_methods_with_HEAD": {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "enum": ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"],
            }
        },
        "required": ["method"],
    },
    "enum_untyped_with_HEAD": {
        "type": "object",
        "properties": {"method": {"enum": ["GET", "HEAD"]}},
        "required": ["method"],
    },
    "enum_integer": {
        "type": "object",
        "properties": {"level": {"type": "integer", "enum": [1, 2, 3]}},
    },
    "anyOf_nullable": {
        "type": "object",
        "properties": {"note": {"anyOf": [{"type": "string"}, {"type": "null"}]}},
    },
    "type_list_nullable": {
        "type": "object",
        "properties": {"note": {"type": ["string", "null"]}},
    },
    "oneOf_objects": {
        "type": "object",
        "properties": {
            "target": {
                "oneOf": [
                    {"type": "object", "properties": {"id": {"type": "string"}}},
                    {"type": "object", "properties": {"email": {"type": "string"}}},
                ]
            }
        },
    },
    "untyped_property": {
        "type": "object",
        "properties": {"anything": {"description": "free-form"}},
    },
    "array_without_items": {
        "type": "object",
        "properties": {"ids": {"type": "array"}},
    },
    "free_form_object_additionalProperties": {
        "type": "object",
        "properties": {
            "meta": {"type": "object", "additionalProperties": {"type": "string"}}
        },
    },
    "ref_without_defs": {
        "type": "object",
        "properties": {"cfg": {"$ref": "#/$defs/Missing"}},
    },
    "ref_with_defs": {
        "type": "object",
        "properties": {"cfg": {"$ref": "#/$defs/Cfg"}},
        "$defs": {"Cfg": {"type": "object", "properties": {"a": {"type": "string"}}}},
    },
    "const_value": {
        "type": "object",
        "properties": {"kind": {"const": "issue"}},
    },
    "title_default_format": {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "title": "Limit", "default": 10},
            "since": {"type": "string", "format": "date-time"},
        },
    },
    "reserved_name_from": {
        "type": "object",
        "properties": {"from": {"type": "string"}},
        "required": ["from"],
    },
}


def mk_tool(slug, schema):
    return Tool.model_construct(
        slug=slug, description=f"Synthetic probe {slug}", input_parameters=schema
    )


def _never_execute(*a, **k):
    raise AssertionError("tool execution attempted during declaration build")


def run_openai(tool):
    from composio_openai import OpenAIProvider

    out = OpenAIProvider().wrap_tool(tool)
    return out["function"]["parameters"]


def run_openai_responses_strict(tool):
    from composio.utils.strict_schema import to_strict_json_schema

    res = to_strict_json_schema(tool.input_parameters)
    if res.unsupported:
        raise ValueError(
            "strict-unsupported: "
            + "; ".join(f"{getattr(u, 'path', '?')}: {getattr(u, 'reason', u)}" for u in res.unsupported)
        )
    return {
        "schema": res.schema,
        "changes": [f"{c.path}: {c.reason}" for c in res.changes],
    }


def run_anthropic(tool):
    from composio_anthropic import AnthropicProvider

    return dict(AnthropicProvider().wrap_tool(tool))["input_schema"]


def run_google_vertex(tool):
    from composio_google import GoogleProvider

    decl = GoogleProvider().wrap_tool(tool)
    return decl.to_dict().get("parameters")


def run_gemini_genai(tool):
    from composio_gemini import GeminiProvider
    from google import genai
    from google.genai import types as gt

    func = GeminiProvider().wrap_tool(tool, _never_execute)
    decl = gt.FunctionDeclaration.from_callable(
        client=genai.Client(api_key="offline-test")._api_client, callable=func
    )
    return decl.parameters.model_dump(exclude_none=True, mode="json") if decl.parameters else None


def run_google_adk(tool):
    from composio_google_adk import GoogleAdkProvider

    wrapped = GoogleAdkProvider().wrap_tool(tool, execute_tool=_never_execute)
    decl = wrapped._get_declaration()
    if decl.parameters_json_schema is not None:
        return {"parameters_json_schema": decl.parameters_json_schema}
    return {"parameters": decl.parameters.model_dump(exclude_none=True, mode="json") if decl.parameters else None}


PROVIDERS = {
    "openai": run_openai,
    "openai_responses_strict": run_openai_responses_strict,
    "anthropic": run_anthropic,
    "google_vertex(composio_google)": run_google_vertex,
    "gemini_genai(composio_gemini)": run_gemini_genai,
    "google_adk(composio_google_adk)": run_google_adk,
}

KEYWORDS = ("examples", "file_uploadable", "enum", "anyOf", "oneOf", "$ref", "const", "title", "default", "format", "additionalProperties", "items")


def keywords_present(obj, found=None):
    found = set() if found is None else found
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in KEYWORDS:
                found.add(k)
            keywords_present(v, found)
    elif isinstance(obj, list):
        for v in obj:
            keywords_present(v, found)
    return found


def main():
    import os

    selected = sys.argv[1:] or list(CASES)
    only = [p for p in os.environ.get("REPRO_PROVIDERS", "").split(",") if p]
    providers = {k: v for k, v in PROVIDERS.items() if not only or any(k.startswith(o) for o in only)}
    results = []
    for case in selected:
        schema = CASES[case]
        in_kw = keywords_present(schema)
        for pname, fn in providers.items():
            rec = {"case": case, "provider": pname}
            try:
                out = fn(mk_tool(case.upper(), json.loads(json.dumps(schema))))
                out_kw = keywords_present(out)
                rec.update(
                    status="ok",
                    dropped_keywords=sorted(in_kw - out_kw),
                    added_keywords=sorted(out_kw - in_kw),
                    output=json.loads(json.dumps(out, default=str)),
                )
            except Exception as e:  # noqa: BLE001
                rec.update(
                    status="error",
                    error_type=type(e).__name__,
                    error=str(e)[:600],
                    where=traceback.extract_tb(e.__traceback__)[-1].filename.split("site-packages")[-1],
                )
            results.append(rec)
    json.dump(results, sys.stdout, indent=1, default=str)


if __name__ == "__main__":
    main()
