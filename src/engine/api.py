"""Public entrypoint for the PRSpec Engine API.

Usage::

    from src.engine import scan_path

    result = scan_path("path/to/source", ruleset="ethereum")
    print(result["summary"])
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..parser import CodeParser

# Attempt to read the package version; fall back to "dev".
try:
    from src import __version__ as _prspec_version
except Exception:  # pragma: no cover
    _prspec_version = "dev"

# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

_EXT_TO_LANG: Dict[str, str] = {
    ".go": "go",
    ".py": "python",
    ".cs": "csharp",
    ".java": "java",
    ".js": "javascript",
    ".ts": "typescript",
    ".rs": "rust",
    ".sol": "solidity",
}

_IGNORED_DIRS = {
    ".git", "__pycache__", "node_modules", ".tox", ".mypy_cache",
    ".pytest_cache", "venv", ".venv", "env", "build", "dist", "egg-info",
}


def _detect_language(filepath: str) -> Optional[str]:
    ext = Path(filepath).suffix.lower()
    return _EXT_TO_LANG.get(ext)


# ---------------------------------------------------------------------------
# Ethereum ruleset — keyword-based static scan
# ---------------------------------------------------------------------------

# Severity assigned to keyword-match findings (conservative defaults).
_KEYWORD_SEVERITY: Dict[str, str] = {
    "missing": "high",
    "deviation": "high",
    "edge_case": "medium",
    "info": "info",
}

# EIP keyword registry — mirrors CodeParser.EIP_KEYWORDS but kept local so
# the engine module stays self-contained.  We *also* try to import the
# canonical list at runtime so new keywords added to the parser are picked up.
_DEFAULT_EIP_KEYWORDS: Dict[int, List[str]] = {
    1559: [
        "basefee", "base_fee", "gaslimit", "gas_limit",
        "feecap", "fee_cap", "priority",
        "1559", "dynamicfee", "dynamic_fee",
        "calcbasefee", "calc_base_fee", "verifyeip1559",
    ],
    4844: [
        "blob", "4844", "kzg", "shard",
        "blob_gas", "blobgas", "excess_blob_gas",
        "blob_fee", "blobfee", "blobhash",
        "blobsidecar", "blobtx",
    ],
    4788: ["4788", "beacon_root", "beaconroot"],
    2930: ["2930", "access_list", "accesslist"],
}


def _get_eip_keywords() -> Dict[int, List[str]]:
    """Return the canonical keyword map, falling back to defaults."""
    try:
        from ..parser import CodeParser as _CP
        return dict(_CP.EIP_KEYWORDS)
    except Exception:
        return dict(_DEFAULT_EIP_KEYWORDS)


def _discover_files(root: str) -> List[str]:
    """Recursively find analyzable source files under *root*."""
    root_path = Path(root)
    if root_path.is_file():
        return [str(root_path)]

    results: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune ignored directories in-place
        dirnames[:] = [d for d in dirnames if d not in _IGNORED_DIRS]
        for fname in filenames:
            full = os.path.join(dirpath, fname)
            if _detect_language(full) is not None:
                results.append(full)
    return sorted(results)


# ---------------------------------------------------------------------------
# scan_path — the single public entrypoint
# ---------------------------------------------------------------------------

def scan_path(
    target_path: str,
    *,
    ruleset: str = "ethereum",
    output: str = "json",
) -> Dict[str, Any]:
    """Scan *target_path* for Ethereum spec-compliance issues.

    Parameters
    ----------
    target_path:
        File or directory to scan.
    ruleset:
        Rule family to apply.  Currently only ``"ethereum"`` is supported.
    output:
        Desired output format.  ``"json"`` returns the raw dict.
        ``"json-pretty"`` returns the dict with a serialised ``_json`` key.

    Returns
    -------
    dict
        A :class:`~src.engine.models.ScanResult` compatible dict.
    """
    target = Path(target_path)
    if not target.exists():
        raise FileNotFoundError(f"Target path does not exist: {target_path}")

    files = _discover_files(target_path)
    parser = CodeParser()
    eip_keywords = _get_eip_keywords()

    findings: List[Dict[str, Any]] = []
    finding_id = 0

    for fpath in files:
        lang = _detect_language(fpath)
        if lang is None:
            continue

        try:
            content = Path(fpath).read_text(errors="replace")
        except OSError:
            continue

        blocks = parser.parse_file(content, lang)

        # Check each block against every known EIP keyword set
        for eip_num, keywords in eip_keywords.items():
            for block in blocks:
                name_lower = block.name.lower()
                content_lower = block.content.lower()

                matched_keywords: List[str] = []
                for kw in keywords:
                    if kw in name_lower or kw in content_lower:
                        matched_keywords.append(kw)

                if matched_keywords:
                    finding_id += 1
                    # Determine a relative path for readability
                    try:
                        rel = os.path.relpath(fpath, target_path)
                    except ValueError:
                        rel = fpath

                    findings.append({
                        "id": f"PRSPEC-{finding_id:04d}",
                        "severity": "info",
                        "title": f"EIP-{eip_num} relevant code block",
                        "message": (
                            f"{block.type.capitalize()} '{block.name}' "
                            f"matches EIP-{eip_num} keywords: "
                            f"{', '.join(sorted(set(matched_keywords)))}"
                        ),
                        "file": rel,
                        "line": block.start_line,
                        "hint": (
                            f"Run full PRSpec LLM analysis for detailed "
                            f"compliance checking of EIP-{eip_num}."
                        ),
                    })

    # Build summary
    high = sum(1 for f in findings if f["severity"] == "high")
    med = sum(1 for f in findings if f["severity"] == "medium")
    low = sum(1 for f in findings if f["severity"] == "low")
    info = sum(1 for f in findings if f["severity"] == "info")

    result: Dict[str, Any] = {
        "tool": "PRSpec",
        "tool_version": _prspec_version,
        "ruleset": ruleset,
        "findings": findings,
        "summary": {
            "high": high,
            "med": med,
            "low": low,
            "info": info,
            "files_scanned": len(files),
        },
    }

    if output == "json-pretty":
        result["_json"] = json.dumps(result, indent=2)

    return result
