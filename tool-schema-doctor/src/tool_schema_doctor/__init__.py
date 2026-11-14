"""Tool-Schema Doctor: offline QA for Composio tool schemas.

Public API:
    load_tools(path)            -> list[ToolRecord]
    run_compatibility(records)  -> list[CompatResult]
    available_providers()       -> dict[str, bool]
"""

from .model import CompatResult, LintFinding, Report, ToolRecord
from .loader import load_tools
from .compat import run_compatibility
from .providers import available_providers, PROVIDER_IDS

__version__ = "0.1.0"

__all__ = [
    "ToolRecord",
    "CompatResult",
    "LintFinding",
    "Report",
    "load_tools",
    "run_compatibility",
    "available_providers",
    "PROVIDER_IDS",
    "__version__",
]
