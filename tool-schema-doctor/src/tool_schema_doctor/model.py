"""Dataclasses for Tool-Schema Doctor results. Stdlib only."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Optional


# Compatibility statuses
OK = "ok"                    # converted without dropping tracked keywords
TRANSFORMED = "transformed"  # converted, but tracked keywords dropped/added
ERROR = "error"              # the real adapter raised
UNAVAILABLE = "unavailable"  # provider SDK not installed (skipped, not a failure)
SKIPPED = "skipped"          # not applicable (e.g. no schema in the input record)

# Lint severities
SEV_ERROR = "error"
SEV_WARNING = "warning"
SEV_INFO = "info"


@dataclass
class ToolRecord:
    """A normalized tool from a fixture (mock) or catalog input."""

    slug: str
    name: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    input_parameters: Optional[dict] = None
    toolkit: Optional[str] = None
    source: str = "unknown"  # which fixture shape this came from

    @property
    def has_schema(self) -> bool:
        return isinstance(self.input_parameters, dict)

    @property
    def has_tags(self) -> bool:
        return bool(self.tags)


@dataclass
class CompatResult:
    slug: str
    provider: str
    status: str
    error_type: Optional[str] = None
    message: Optional[str] = None
    schema_path: Optional[str] = None
    where: Optional[str] = None
    dropped_keywords: list[str] = field(default_factory=list)
    added_keywords: list[str] = field(default_factory=list)


@dataclass
class LintFinding:
    rule_id: str
    severity: str
    slug: str
    message: str
    toolkit: Optional[str] = None
    field_path: Optional[str] = None
    evidence: Optional[str] = None
    remediation: Optional[str] = None


@dataclass
class Report:
    meta: dict = field(default_factory=dict)
    compatibility: list[CompatResult] = field(default_factory=list)
    lint: list[LintFinding] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


def to_jsonable(obj: Any) -> Any:
    """Recursively convert dataclasses to plain dicts for json.dump."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: to_jsonable(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    return obj
