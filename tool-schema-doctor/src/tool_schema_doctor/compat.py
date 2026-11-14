"""Run tool records through provider adapters and classify each outcome."""

from __future__ import annotations

import contextlib
from typing import Iterable, Optional

from . import providers
from .model import (
    CompatResult, ToolRecord,
    OK, TRANSFORMED, ERROR, UNAVAILABLE, SKIPPED,
)


# Adapter messages are evidence, so keep them whole. The cap only guards against
# pathological output, and any cut is labelled rather than silent.
MESSAGE_LIMIT = 4000


def clip_message(text: str, limit: int = MESSAGE_LIMIT) -> str:
    """Return `text` unchanged, or cut at `limit` with an explicit marker."""
    if len(text) <= limit:
        return text
    return f"{text[:limit]} …[truncated {len(text) - limit} chars]"


def _schema_path_for_error(provider_id: str, params: dict, exc: BaseException) -> Optional[str]:
    """Best-effort: locate the schema element that likely caused the failure."""
    if provider_id == "google_vertex":
        # Vertex strips top-level examples; failure comes from nested examples or file_uploadable.
        fu = providers.first_path(params, "file_uploadable")
        if fu:
            return fu
        return providers.first_path(params, "examples", nested_only=True)
    if provider_id == "gemini":
        # google-genai names the offending parameter in the message: "parameter <name>".
        msg = str(exc)
        marker = "parameter "
        if marker in msg:
            name = msg.split(marker, 1)[1].split(":")[0].strip()
            if name:
                return f"/properties/{name}"
    return None


def run_one(record: ToolRecord, provider_id: str) -> CompatResult:
    """Convert one record with one provider. Never raises."""
    if not record.has_schema:
        return CompatResult(record.slug, provider_id, SKIPPED,
                            message="no input_parameters in this record")
    params = record.input_parameters or {}
    in_kw = providers.keywords_present(params)
    try:
        out = providers.convert(provider_id, record.slug, record.description, params)
    except (ImportError, ModuleNotFoundError) as e:
        return CompatResult(record.slug, provider_id, UNAVAILABLE,
                            error_type=type(e).__name__, message=clip_message(str(e)))
    except Exception as e:  # noqa: BLE001 - adapters raise many types
        return CompatResult(
            record.slug, provider_id, ERROR,
            error_type=type(e).__name__,
            message=clip_message(str(e)),
            schema_path=_schema_path_for_error(provider_id, params, e),
            where=providers.last_frame(e),
        )
    out_kw = providers.keywords_present(out)
    dropped = sorted(in_kw - out_kw)
    added = sorted(out_kw - in_kw)
    status = TRANSFORMED if (dropped or added) else OK
    return CompatResult(record.slug, provider_id, status,
                        dropped_keywords=dropped, added_keywords=added)


def run_compatibility(
    records: Iterable[ToolRecord],
    provider_ids: Optional[list[str]] = None,
    *,
    offline: bool = True,
) -> list[CompatResult]:
    """Run the corpus x providers. One failing tool never stops the run.

    Providers whose SDK is missing are reported `unavailable` once and skipped
    for the remaining tools (not counted as schema failures).

    With offline=True the network is blocked only while this call runs.
    """
    with (providers.offline() if offline else contextlib.nullcontext()):
        return _run_compatibility(list(records), provider_ids)


def _run_compatibility(records: list[ToolRecord], provider_ids: Optional[list[str]]) -> list[CompatResult]:
    if provider_ids is None:
        avail = providers.available_providers()
        provider_ids = [p for p in providers.PROVIDER_IDS if avail.get(p)]
        missing = [p for p in providers.PROVIDER_IDS if not avail.get(p)]
    else:
        missing = []

    results: list[CompatResult] = []

    # Report explicitly-missing providers once.
    for pid in missing:
        results.append(CompatResult("*", pid, UNAVAILABLE,
                                    message="provider SDK not installed"))

    unavailable_now: set[str] = set()
    for pid in provider_ids:
        if pid in unavailable_now:
            continue
        for rec in records:
            res = run_one(rec, pid)
            results.append(res)
            if res.status == UNAVAILABLE and res.slug != "*":
                # SDK missing: mark provider, stop hammering it.
                unavailable_now.add(pid)
                break
    return results


def summarize(results: list[CompatResult]) -> dict:
    """Counts by provider and status."""
    summary: dict[str, dict[str, int]] = {}
    for r in results:
        d = summary.setdefault(r.provider, {})
        d[r.status] = d.get(r.status, 0) + 1
    return summary
