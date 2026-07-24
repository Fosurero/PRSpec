"""Aggregation of per-file analysis results into summary statistics.

Shared by the report generator (single-client reports) and the differential
engine (cross-client comparison), which need the same severity/status rollup.
"""

from typing import Any, Dict, List

from .verifier import confirmed_issues


def summarize_results(results: List[Dict[str, Any]],
                      confirmed_only: bool = False,
                      count_verification: bool = False,
                      count_issue_types: bool = False) -> Dict[str, Any]:
    """Aggregate per-file analysis dicts into summary stats.

    When *confirmed_only* is set and the results carry verification verdicts,
    only CONFIRMED findings are counted, so stats reflect what survived
    adversarial verification rather than raw candidates.  *count_verification*
    adds a ``verification`` verdict tally and *count_issue_types* an
    ``issue_types`` breakdown.
    """
    total_issues = 0
    high = med = low = 0
    confidences: List[int] = []
    statuses: List[str] = []
    type_counts: Dict[str, int] = {}
    verification = {"verified": False, "confirmed": 0, "disputed": 0, "refuted": 0}

    for result in results:
        issues = confirmed_issues(result) if confirmed_only else (result.get("issues", []) or [])
        total_issues += len(issues)
        for issue in issues:
            severity = str(issue.get("severity", "")).upper()
            if severity == "HIGH":
                high += 1
            elif severity == "MEDIUM":
                med += 1
            elif severity == "LOW":
                low += 1

            if count_issue_types:
                itype = str(issue.get("type", "")).upper()
                if itype:
                    type_counts[itype] = type_counts.get(itype, 0) + 1

            if count_verification:
                verdict = issue.get("verification", {}).get("verdict")
                if verdict:
                    verification["verified"] = True
                    key = verdict.lower()
                    if key in verification:
                        verification[key] += 1

        confidences.append(int(result.get("confidence", 0) or 0))
        statuses.append(str(result.get("status", "UNKNOWN")))

    if "MISSING" in statuses or high > 0:
        overall = "ISSUES FOUND"
    elif "PARTIAL_MATCH" in statuses or med > 0:
        overall = "PARTIAL"
    elif statuses and all(s == "FULL_MATCH" for s in statuses):
        overall = "COMPLIANT"
    else:
        overall = "UNCERTAIN"

    summary: Dict[str, Any] = {
        "overall_status": overall,
        "average_confidence": round(sum(confidences) / len(confidences)) if confidences else 0,
        "files_analyzed": len(results),
        "total_issues": total_issues,
        "high_severity": high,
        "medium_severity": med,
        "low_severity": low,
    }
    if count_issue_types:
        summary["issue_types"] = type_counts
    if count_verification:
        summary["verification"] = verification
    return summary
