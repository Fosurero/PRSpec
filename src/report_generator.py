"""Report generation — JSON, Markdown, and HTML compliance reports."""

import html
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

try:
    from rich import box
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


from src import __version__

_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]")


def _slug(value: Any) -> str:
    """Filename-safe rendering of a report identifier (EIP, client name, ...)."""
    return _UNSAFE_FILENAME_CHARS.sub("_", str(value))


@dataclass
class ReportMetadata:
    """Metadata for a compliance report"""
    title: str
    eip_number: int
    client: str
    timestamp: datetime
    analyzer: str
    version: str = __version__


class ReportGenerator:
    """Generates compliance reports in various formats"""

    def __init__(self, output_dir: str = "output"):
        """Create output directory if it doesn't exist."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if RICH_AVAILABLE:
            self.console = Console()
        else:
            self.console = None

    def generate_report(self, results: List[Dict[str, Any]],
                       metadata: ReportMetadata,
                       format: str = "json") -> str:
        """Write a report in the requested format and return the file path."""
        format = format.lower()

        if format == "json":
            return self._generate_json_report(results, metadata)
        elif format == "markdown" or format == "md":
            return self._generate_markdown_report(results, metadata)
        elif format == "html":
            return self._generate_html_report(results, metadata)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _generate_json_report(self, results: List[Dict[str, Any]],
                              metadata: ReportMetadata) -> str:
        """Generate JSON format report"""
        report = {
            "metadata": {
                "title": metadata.title,
                "eip_number": metadata.eip_number,
                "client": metadata.client,
                "timestamp": metadata.timestamp.isoformat(),
                "analyzer": metadata.analyzer,
                "version": metadata.version,
            },
            "summary": self._generate_summary(results),
            "results": results
        }

        filename = f"prspec_eip{_slug(metadata.eip_number)}_{_slug(metadata.client)}_{metadata.timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.output_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)

        return str(filepath)

    def _generate_markdown_report(self, results: List[Dict[str, Any]],
                                  metadata: ReportMetadata) -> str:
        """Generate Markdown format report"""
        summary = self._generate_summary(results)
        verification = summary.get("verification", {})
        verified_row = ""
        if verification.get("verified"):
            verified_row = (
                f"| Verified | {verification['confirmed']} confirmed, "
                f"{verification['disputed']} disputed, "
                f"{verification['refuted']} refuted |"
            )

        md_content = f"""# {metadata.title}

## Report Information

| Field | Value |
|-------|-------|
| EIP | {metadata.eip_number} |
| Client | {metadata.client} |
| Analyzer | {metadata.analyzer} |
| Generated | {metadata.timestamp.strftime('%Y-%m-%d %H:%M:%S')} |
| Version | {metadata.version} |

## Executive Summary

{self._build_narrative(results, metadata)}

| Metric | Value |
|--------|-------|
| Status | {summary['overall_status']} |
| Confidence | {summary['average_confidence']}% |
| Files analysed | {summary['files_analyzed']} |
| Issues | {summary['total_issues']} (H:{summary['high_severity']} M:{summary['medium_severity']} L:{summary['low_severity']}) |
{verified_row}

## Detailed Findings

"""

        for i, result in enumerate(results, 1):
            md_content += f"""### {i}. {result.get('file_name', 'Unknown File')}

**Status**: {result.get('status', 'UNKNOWN')} | **Confidence**: {result.get('confidence', 0)}%

{result.get('summary', 'No summary available.')}

"""
            issues = result.get('issues', [])
            if issues:
                md_content += "#### Issues Found\n\n"
                for j, issue in enumerate(issues, 1):
                    verdict = self._verdict_text(issue)
                    verdict_md = f"- **Verification**: {verdict}\n" if verdict else ""
                    md_content += f"""**{j}. [{issue.get('severity', 'UNKNOWN')}] {issue.get('type', 'Issue')}**

{verdict_md}- **Description**: {issue.get('description', 'N/A')}
- **Spec Reference**: `{issue.get('spec_reference', 'N/A')}`
- **Code Location**: `{issue.get('code_location', 'N/A')}`
- **Potential Impact**: {issue.get('potential_impact', 'N/A')}
- **Suggestion**: {issue.get('suggestion', 'N/A')}

"""
            else:
                md_content += "No issues found in this file.\n\n"

            md_content += "---\n\n"

        md_content += f"""
## Methodology

This report was generated using PRSpec, an Ethereum specification compliance checker.
The analysis was performed using {metadata.analyzer} to compare the implementation
against the official EIP-{metadata.eip_number} specification.

---

*Generated by PRSpec v{metadata.version}*
"""

        filename = f"prspec_eip{_slug(metadata.eip_number)}_{_slug(metadata.client)}_{metadata.timestamp.strftime('%Y%m%d_%H%M%S')}.md"
        filepath = self.output_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md_content)

        return str(filepath)

    def _generate_html_report(self, results: List[Dict[str, Any]],
                              metadata: ReportMetadata) -> str:
        """Generate HTML format report"""
        summary = self._generate_summary(results)

        status_colors = {
            "FULL_MATCH": "#28a745",
            "PARTIAL_MATCH": "#ffc107",
            "MISSING": "#dc3545",
            "UNCERTAIN": "#6c757d",
            "ERROR": "#dc3545",
        }

        verification = summary.get("verification", {})
        verified_kpi = ""
        if verification.get("verified"):
            verified_kpi = (
                f'<div class="kpi"><div class="num" style="color:#1a73e8">'
                f'{verification["confirmed"]}</div>'
                f'<div class="lbl">Confirmed</div></div>'
            )

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(metadata.title)}</title>
    <style>
        *, *::before, *::after {{ box-sizing: border-box; }}
        body {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; background: #f0f2f5; color: #1a1a2e; line-height: 1.6; }}
        .page {{ max-width: 960px; margin: 40px auto; padding: 0 20px; }}
        header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: #fff; padding: 36px 40px; border-radius: 12px 12px 0 0; }}
        header h1 {{ margin: 0 0 6px; font-size: 1.6em; font-weight: 700; }}
        header .meta {{ font-size: 0.85em; opacity: 0.8; }}
        .body {{ background: #fff; padding: 32px 40px; border-radius: 0 0 12px 12px; box-shadow: 0 4px 24px rgba(0,0,0,0.06); }}
        .kpi-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 16px; margin-bottom: 32px; }}
        .kpi {{ background: #f8f9fb; border: 1px solid #e8eaed; border-radius: 8px; padding: 18px 14px; text-align: center; }}
        .kpi .num {{ font-size: 1.7em; font-weight: 700; }}
        .kpi .lbl {{ font-size: 0.78em; color: #666; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 4px; }}
        h2 {{ font-size: 1.15em; font-weight: 600; color: #333; border-bottom: 2px solid #e8eaed; padding-bottom: 8px; margin: 28px 0 18px; }}
        .file-card {{ border: 1px solid #e0e3e8; border-radius: 8px; margin-bottom: 20px; overflow: hidden; }}
        .file-card .head {{ display: flex; justify-content: space-between; align-items: center; padding: 12px 18px; background: #fafbfc; border-bottom: 1px solid #e0e3e8; }}
        .file-card .head .path {{ font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', monospace; font-size: 0.88em; font-weight: 500; }}
        .badge {{ display: inline-block; padding: 3px 12px; border-radius: 12px; color: #fff; font-size: 0.75em; font-weight: 600; text-transform: uppercase; letter-spacing: 0.3px; }}
        .file-card .content {{ padding: 16px 18px; }}
        .file-card .content p {{ margin: 0 0 10px; }}
        .issue {{ border-left: 3px solid; padding: 12px 16px; margin: 12px 0; border-radius: 0 6px 6px 0; background: #fafbfc; }}
        .issue-high {{ border-color: #e03e3e; background: #fef2f2; }}
        .issue-medium {{ border-color: #d4a017; background: #fffbeb; }}
        .issue-low {{ border-color: #2e7d32; background: #f0fdf4; }}
        .issue .title {{ font-weight: 600; margin-bottom: 6px; font-size: 0.92em; }}
        .issue .detail {{ font-size: 0.85em; color: #555; margin: 3px 0; }}
        .issue .detail strong {{ color: #333; }}
        code {{ background: #eef0f4; padding: 1px 5px; border-radius: 3px; font-family: 'SFMono-Regular', Consolas, monospace; font-size: 0.88em; }}
        .footer {{ text-align: center; padding: 24px 0 0; margin-top: 32px; border-top: 1px solid #e8eaed; font-size: 0.8em; color: #888; }}
    </style>
</head>
<body>
<div class="page">
    <header>
        <h1>{html.escape(metadata.title)}</h1>
        <div class="meta">{metadata.timestamp.strftime('%Y-%m-%d %H:%M')} &middot; {html.escape(metadata.analyzer)} &middot; v{html.escape(metadata.version)}</div>
    </header>
    <div class="body">
        <div class="kpi-row">
            <div class="kpi"><div class="num">{html.escape(str(summary['overall_status']))}</div><div class="lbl">Status</div></div>
            <div class="kpi"><div class="num">{summary['average_confidence']}%</div><div class="lbl">Confidence</div></div>
            <div class="kpi"><div class="num">{summary['files_analyzed']}</div><div class="lbl">Files</div></div>
            <div class="kpi"><div class="num" style="color:#e03e3e">{summary['high_severity']}</div><div class="lbl">High</div></div>
            <div class="kpi"><div class="num" style="color:#d4a017">{summary['medium_severity']}</div><div class="lbl">Medium</div></div>
            <div class="kpi"><div class="num" style="color:#2e7d32">{summary['low_severity']}</div><div class="lbl">Low</div></div>
            {verified_kpi}
        </div>

        <div style="background:#f8f9fb;border:1px solid #e8eaed;border-radius:8px;padding:18px 22px;margin-bottom:28px;font-size:0.93em;line-height:1.7;white-space:pre-line;">{html.escape(self._build_narrative(results, metadata))}</div>

        <h2>Findings</h2>
"""

        for result in results:
            status = str(result.get('status', 'UNKNOWN'))
            status_color = status_colors.get(status, '#6c757d')

            html_content += f"""
        <div class="file-card">
            <div class="head">
                <span class="path">{html.escape(str(result.get('file_name', 'Unknown File')))}</span>
                <span class="badge" style="background:{status_color}">{html.escape(str(status))}</span>
            </div>
            <div class="content">
                <p><strong>Confidence:</strong> {html.escape(str(result.get('confidence', 0)))}%</p>
                <p>{html.escape(result.get('summary', 'No summary available.'))}</p>
"""

            issues = result.get('issues', [])
            if issues:
                for issue in issues:
                    severity = issue.get('severity', 'LOW').lower()
                    verdict_html = self._verdict_badge_html(issue)
                    html_content += f"""
                <div class="issue issue-{html.escape(severity)}">
                    <div class="title">[{html.escape(issue.get('severity', '?'))}] {html.escape(issue.get('type', 'Issue'))}</div>
                    {verdict_html}
                    <div class="detail"><strong>Description:</strong> {html.escape(issue.get('description', 'N/A'))}</div>
                    <div class="detail"><strong>Spec ref:</strong> <code>{html.escape(issue.get('spec_reference', 'N/A'))}</code></div>
                    <div class="detail"><strong>Location:</strong> <code>{html.escape(issue.get('code_location', 'N/A'))}</code></div>
                    <div class="detail"><strong>Impact:</strong> {html.escape(issue.get('potential_impact', 'N/A'))}</div>
                    <div class="detail"><strong>Fix:</strong> {html.escape(issue.get('suggestion', 'N/A'))}</div>
                </div>
"""
            else:
                html_content += "                <p>No issues found.</p>"

            html_content += """
            </div>
        </div>
"""

        html_content += f"""
        <div class="footer">
            PRSpec v{html.escape(metadata.version)} &middot; {html.escape(metadata.analyzer)} &middot; EIP-{html.escape(str(metadata.eip_number))} &middot; {html.escape(metadata.client)} &middot; {metadata.timestamp.strftime('%Y-%m-%d %H:%M')}
        </div>
    </div>
</div>
</body>
</html>
"""

        filename = f"prspec_eip{_slug(metadata.eip_number)}_{_slug(metadata.client)}_{metadata.timestamp.strftime('%Y%m%d_%H%M%S')}.html"
        filepath = self.output_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return str(filepath)

    def _build_narrative(self, results: List[Dict[str, Any]],
                          metadata: ReportMetadata) -> str:
        """Build a short, readable paragraph summarising the analysis."""
        s = self._generate_summary(results)
        n_files = s['files_analyzed']
        total = s['total_issues']

        # Opening sentence
        parts = [
            f"PRSpec analysed {n_files} file{'s' if n_files != 1 else ''} from "
            f"{metadata.client}'s EIP-{metadata.eip_number} implementation "
            f"using {metadata.analyzer}."
        ]

        # Verdict
        parts.append(
            f"Overall verdict: {s['overall_status']} "
            f"at {s['average_confidence']}% average confidence."
        )

        # Issue breakdown (only when there are issues)
        if total:
            severity_bits = []
            if s['high_severity']:
                severity_bits.append(f"{s['high_severity']} high")
            if s['medium_severity']:
                severity_bits.append(f"{s['medium_severity']} medium")
            if s['low_severity']:
                severity_bits.append(f"{s['low_severity']} low")
            parts.append(
                f"{total} issue{'s' if total != 1 else ''} detected "
                f"({', '.join(severity_bits)})."
            )
        else:
            parts.append("No compliance issues were detected.")

        # Per-file one-liners
        for r in results:
            fname = r.get('file_name', '?')
            fstatus = r.get('status', '?')
            n_issues = len(r.get('issues', []))
            short = r.get('summary', '')[:120]
            if short:
                parts.append(f"{fname} — {fstatus} ({n_issues} issues): {short}")

        return " ".join(parts[:3]) + "\n\n" + "\n".join(parts[3:])

    # Colors for verification verdicts, shared across HTML rendering.
    _VERDICT_COLORS = {"CONFIRMED": "#1a73e8", "DISPUTED": "#d4a017", "REFUTED": "#888"}

    def _verdict_text(self, issue: Dict[str, Any]) -> str:
        """Plain-text verdict summary for an issue, or '' if unverified."""
        v = issue.get("verification")
        if not v or not v.get("verdict"):
            return ""
        grounded = "grounded ✓" if v.get("grounded") else "ungrounded ✗"
        return f"{v['verdict']} · {v.get('verification_score', 0)}/100 · {grounded}"

    def _verdict_badge_html(self, issue: Dict[str, Any]) -> str:
        """Render a verification verdict badge for an issue, or '' if unverified."""
        v = issue.get("verification")
        if not v or not v.get("verdict"):
            return ""
        verdict = v["verdict"]
        color = self._VERDICT_COLORS.get(verdict, "#888")
        grounded = "grounded ✓" if v.get("grounded") else "ungrounded ✗"
        return (
            f'<div class="detail"><span class="badge" style="background:{color}">'
            f'{html.escape(verdict)}</span> '
            f'<span style="color:#666;font-size:0.85em">'
            f'{html.escape(str(v.get("verification_score", 0)))}/100 &middot; {grounded}</span></div>'
        )

    def _generate_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary statistics from results"""
        total_issues = 0
        high_severity = 0
        medium_severity = 0
        low_severity = 0
        confidences = []
        statuses = []
        verification = {"verified": False, "confirmed": 0,
                        "disputed": 0, "refuted": 0}

        for result in results:
            issues = result.get('issues', [])
            total_issues += len(issues)

            for issue in issues:
                severity = issue.get('severity', '').upper()
                if severity == 'HIGH':
                    high_severity += 1
                elif severity == 'MEDIUM':
                    medium_severity += 1
                elif severity == 'LOW':
                    low_severity += 1

                verdict = issue.get('verification', {}).get('verdict')
                if verdict:
                    verification["verified"] = True
                    key = verdict.lower()
                    if key in verification:
                        verification[key] += 1

            confidences.append(result.get('confidence', 0))
            statuses.append(result.get('status', 'UNKNOWN'))

        # Determine overall status
        if 'MISSING' in statuses or high_severity > 0:
            overall_status = "ISSUES FOUND"
        elif 'PARTIAL_MATCH' in statuses or medium_severity > 0:
            overall_status = "PARTIAL"
        elif all(s == 'FULL_MATCH' for s in statuses):
            overall_status = "COMPLIANT"
        else:
            overall_status = "UNCERTAIN"

        return {
            "overall_status": overall_status,
            "average_confidence": round(sum(confidences) / len(confidences)) if confidences else 0,
            "files_analyzed": len(results),
            "total_issues": total_issues,
            "high_severity": high_severity,
            "medium_severity": medium_severity,
            "low_severity": low_severity,
            "verification": verification,
        }

    # ------------------------------------------------------------------
    # Cross-client differential reports
    # ------------------------------------------------------------------

    def generate_differential_report(self, differential: Any,
                                     format: str = "json") -> str:
        """Write a cross-client differential report and return the file path.

        *differential* is a :class:`src.differential.DifferentialResult`.
        """
        format = format.lower()
        if format == "json":
            return self._generate_differential_json(differential)
        elif format in ("markdown", "md"):
            return self._generate_differential_markdown(differential)
        elif format == "html":
            return self._generate_differential_html(differential)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _diff_filename(self, differential: Any, ext: str) -> Path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.output_dir / f"prspec_diff_eip{_slug(differential.eip)}_{stamp}.{ext}"

    def _generate_differential_json(self, differential: Any) -> str:
        filepath = self._diff_filename(differential, "json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(differential.to_dict(), f, indent=2)
        return str(filepath)

    def _generate_differential_markdown(self, differential: Any) -> str:
        d = differential
        clients = d.clients

        md = [f"# Cross-Client Differential — {d.eip_title}\n"]
        md.append("## Clients Compared\n")
        md.append("| Client | Status | Confidence | Issues (H/M/L) | Files |")
        md.append("|--------|--------|-----------|----------------|-------|")
        for c in clients:
            s = d.client_summaries[c]
            md.append(
                f"| {c} | {s['overall_status']} | {s['average_confidence']}% | "
                f"{s['total_issues']} ({s['high_severity']}/{s['medium_severity']}/"
                f"{s['low_severity']}) | {s['files_analyzed']} |"
            )

        md.append("\n## Executive Summary\n")
        md.append(d.narrative + "\n")
        if d.llm_synthesis:
            md.append("### LLM Synthesis\n")
            md.append(d.llm_synthesis + "\n")

        md.append("## Comparison Matrix\n")
        header = "| Dimension | " + " | ".join(clients) + " | Verdict |"
        sep = "|" + "---|" * (len(clients) + 2)
        md.append(header)
        md.append(sep)
        for row in d.rows:
            cells = " | ".join(row.per_client.get(c, "—") for c in clients)
            md.append(f"| {row.dimension} | {cells} | {row.verdict} |")

        if d.divergences:
            md.append("\n## Divergences\n")
            for note in d.divergences:
                md.append(f"- {note}")

        if d.agreements:
            md.append("\n## Agreements\n")
            for note in d.agreements:
                md.append(f"- {note}")

        md.append(f"\n---\n\n*Generated by PRSpec v{__version__}*\n")

        filepath = self._diff_filename(differential, "md")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(md))
        return str(filepath)

    def _generate_differential_html(self, differential: Any) -> str:
        d = differential
        clients = d.clients
        verdict_colors = {"AGREE": "#2e7d32", "DIVERGE": "#e03e3e"}
        cell_colors = {"flagged": "#e03e3e", "clean": "#2e7d32"}

        # Client KPI cards
        kpi_cards = ""
        for c in clients:
            s = d.client_summaries[c]
            kpi_cards += (
                f'<div class="kpi"><div class="num">{html.escape(c)}</div>'
                f'<div class="lbl">{html.escape(str(s["overall_status"]))} '
                f'&middot; {html.escape(str(s["average_confidence"]))}%</div>'
                f'<div class="lbl">{html.escape(str(s["total_issues"]))} issues '
                f'(H{html.escape(str(s["high_severity"]))}/M{html.escape(str(s["medium_severity"]))}/'
                f'L{html.escape(str(s["low_severity"]))})</div></div>'
            )

        # Comparison table
        head_cells = "".join(f"<th>{html.escape(c)}</th>" for c in clients)
        rows_html = ""
        for row in d.rows:
            color = verdict_colors.get(row.verdict, "#6c757d")
            cells = ""
            for c in clients:
                val = row.per_client.get(c, "—")
                cell_color = cell_colors.get(val, "")
                style = f' style="color:{cell_color};font-weight:600"' if cell_color else ""
                cells += f"<td{style}>{html.escape(str(val))}</td>"
            rows_html += (
                f"<tr><td class='dim'>{html.escape(row.dimension)}</td>{cells}"
                f"<td><span class='badge' style='background:{color}'>"
                f"{html.escape(str(row.verdict))}</span></td></tr>"
            )

        divergences_html = ""
        if d.divergences:
            items = "".join(f"<li>{html.escape(n)}</li>" for n in d.divergences)
            divergences_html = f"<h2>Divergences</h2><ul class='notes'>{items}</ul>"

        synthesis_html = ""
        if d.llm_synthesis:
            synthesis_html = (
                "<h2>LLM Synthesis</h2>"
                f"<div class='narrative'>{html.escape(d.llm_synthesis)}</div>"
            )

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cross-Client Differential — {html.escape(d.eip_title)}</title>
    <style>
        *, *::before, *::after {{ box-sizing: border-box; }}
        body {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; background: #f0f2f5; color: #1a1a2e; line-height: 1.6; }}
        .page {{ max-width: 1040px; margin: 40px auto; padding: 0 20px; }}
        header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: #fff; padding: 36px 40px; border-radius: 12px 12px 0 0; }}
        header h1 {{ margin: 0 0 6px; font-size: 1.5em; font-weight: 700; }}
        header .meta {{ font-size: 0.85em; opacity: 0.8; }}
        .body {{ background: #fff; padding: 32px 40px; border-radius: 0 0 12px 12px; box-shadow: 0 4px 24px rgba(0,0,0,0.06); }}
        .kpi-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; margin-bottom: 28px; }}
        .kpi {{ background: #f8f9fb; border: 1px solid #e8eaed; border-radius: 8px; padding: 16px 14px; text-align: center; }}
        .kpi .num {{ font-size: 1.2em; font-weight: 700; }}
        .kpi .lbl {{ font-size: 0.75em; color: #666; margin-top: 4px; }}
        h2 {{ font-size: 1.15em; font-weight: 600; color: #333; border-bottom: 2px solid #e8eaed; padding-bottom: 8px; margin: 28px 0 18px; }}
        .narrative {{ background:#f8f9fb; border:1px solid #e8eaed; border-radius:8px; padding:18px 22px; margin-bottom:8px; font-size:0.93em; line-height:1.7; }}
        table.matrix {{ width: 100%; border-collapse: collapse; font-size: 0.88em; }}
        table.matrix th, table.matrix td {{ padding: 10px 12px; text-align: center; border-bottom: 1px solid #eceef1; }}
        table.matrix th {{ background: #fafbfc; font-weight: 600; }}
        table.matrix td.dim {{ text-align: left; font-weight: 500; }}
        .badge {{ display: inline-block; padding: 3px 12px; border-radius: 12px; color: #fff; font-size: 0.72em; font-weight: 600; letter-spacing: 0.3px; }}
        ul.notes li {{ margin: 4px 0; font-size: 0.9em; }}
        .footer {{ text-align: center; padding: 24px 0 0; margin-top: 32px; border-top: 1px solid #e8eaed; font-size: 0.8em; color: #888; }}
    </style>
</head>
<body>
<div class="page">
    <header>
        <h1>Cross-Client Differential — {html.escape(d.eip_title)}</h1>
        <div class="meta">{datetime.now().strftime('%Y-%m-%d %H:%M')} &middot; {len(clients)} clients &middot; {d.divergence_count} diverging / {d.agreement_count} agreeing dimensions &middot; v{__version__}</div>
    </header>
    <div class="body">
        <div class="kpi-row">{kpi_cards}</div>
        <div class="narrative">{html.escape(d.narrative)}</div>
        {synthesis_html}
        <h2>Comparison Matrix</h2>
        <table class="matrix">
            <thead><tr><th style="text-align:left">Dimension</th>{head_cells}<th>Verdict</th></tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
        {divergences_html}
        <div class="footer">
            PRSpec v{__version__} &middot; EIP-{d.eip} &middot; {html.escape(', '.join(clients))} &middot; {datetime.now().strftime('%Y-%m-%d %H:%M')}
        </div>
    </div>
</div>
</body>
</html>
"""
        filepath = self._diff_filename(differential, "html")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)
        return str(filepath)

    def print_differential_summary(self, differential: Any):
        """Print a differential summary to the console using Rich."""
        if not RICH_AVAILABLE:
            print(differential.narrative)
            return

        d = differential
        self.console.print(Panel(
            d.narrative + (f"\n\n{d.llm_synthesis}" if d.llm_synthesis else ""),
            title=f"[bold]Cross-Client Differential — {d.eip_title}[/bold]",
            border_style="blue",
            padding=(1, 2),
        ))

        table = Table(title="Comparison Matrix", box=box.ROUNDED)
        table.add_column("Dimension", style="cyan")
        for c in d.clients:
            table.add_column(c, style="white", justify="center")
        table.add_column("Verdict", justify="center")
        for row in d.rows:
            verdict_style = "red" if row.verdict == "DIVERGE" else "green"
            cells = [row.per_client.get(c, "—") for c in d.clients]
            table.add_row(
                row.dimension, *cells,
                f"[{verdict_style}]{row.verdict}[/{verdict_style}]",
            )
        self.console.print(table)
        self.console.print()

        if d.divergences:
            self.console.print("[bold red]Divergences:[/bold red]")
            for note in d.divergences:
                self.console.print(f"  [red]●[/red] {note}")
            self.console.print()

    def print_summary(self, results: List[Dict[str, Any]], metadata: ReportMetadata):
        """Print a summary to the console using Rich"""
        if not RICH_AVAILABLE:
            print("Rich library not available. Install with: pip install rich")
            return

        summary = self._generate_summary(results)
        narrative = self._build_narrative(results, metadata)

        # Narrative box first
        self.console.print(Panel(
            narrative,
            title="[bold]Executive Summary[/bold]",
            border_style="blue",
            padding=(1, 2),
        ))

        # KPI table
        table = Table(title=metadata.title, box=box.ROUNDED)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Overall Status", summary['overall_status'])
        table.add_row("Confidence", f"{summary['average_confidence']}%")
        table.add_row("Files Analyzed", str(summary['files_analyzed']))
        table.add_row("Total Issues", str(summary['total_issues']))
        table.add_row("High Severity", str(summary['high_severity']))
        table.add_row("Medium Severity", str(summary['medium_severity']))
        table.add_row("Low Severity", str(summary['low_severity']))
        verification = summary.get("verification", {})
        if verification.get("verified"):
            table.add_row(
                "Verified",
                f"{verification['confirmed']} confirmed / "
                f"{verification['disputed']} disputed / "
                f"{verification['refuted']} refuted",
            )

        self.console.print(table)
        self.console.print()

        # Print issues
        for result in results:
            issues = result.get('issues', [])
            if issues:
                self.console.print(Panel(
                    f"[bold]{result.get('file_name', 'Unknown')}[/bold]\n{result.get('summary', '')}",
                    title=f"Status: {result.get('status', 'UNKNOWN')}",
                    border_style="yellow" if result.get('status') == 'PARTIAL_MATCH' else "red"
                ))

                for issue in issues:
                    severity = issue.get('severity', 'LOW')
                    color = {'HIGH': 'red', 'MEDIUM': 'yellow', 'LOW': 'green'}.get(severity, 'white')
                    verdict = self._verdict_text(issue)
                    suffix = f" [dim]({verdict})[/dim]" if verdict else ""
                    self.console.print(f"  [{color}]● [{severity}][/{color}] {issue.get('description', 'No description')}{suffix}")

                self.console.print()
