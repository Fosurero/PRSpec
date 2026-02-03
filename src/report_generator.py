"""
Report Generator for PRSpec
Author: Safi El-Hassanine

Generates formatted compliance reports in various formats.
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


@dataclass
class ReportMetadata:
    """Metadata for a compliance report"""
    title: str
    eip_number: int
    client: str
    timestamp: datetime
    analyzer: str
    version: str = "1.0.0"
    author: str = "PRSpec"


class ReportGenerator:
    """Generates compliance reports in various formats"""
    
    def __init__(self, output_dir: str = "output"):
        """
        Initialize the report generator.
        
        Args:
            output_dir: Directory to save reports
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        if RICH_AVAILABLE:
            self.console = Console()
        else:
            self.console = None
    
    def generate_report(self, results: List[Dict[str, Any]], 
                       metadata: ReportMetadata,
                       format: str = "json") -> str:
        """
        Generate a compliance report.
        
        Args:
            results: List of analysis results
            metadata: Report metadata
            format: Output format (json, markdown, html)
            
        Returns:
            Path to generated report file
        """
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
                "author": metadata.author,
            },
            "summary": self._generate_summary(results),
            "results": results
        }
        
        filename = f"prspec_eip{metadata.eip_number}_{metadata.client}_{metadata.timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.output_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
        
        return str(filepath)
    
    def _generate_markdown_report(self, results: List[Dict[str, Any]], 
                                  metadata: ReportMetadata) -> str:
        """Generate Markdown format report"""
        summary = self._generate_summary(results)
        
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

- **Overall Status**: {summary['overall_status']}
- **Confidence**: {summary['average_confidence']}%
- **Files Analyzed**: {summary['files_analyzed']}
- **Total Issues**: {summary['total_issues']}
- **High Severity**: {summary['high_severity']}
- **Medium Severity**: {summary['medium_severity']}
- **Low Severity**: {summary['low_severity']}

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
                    severity_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(issue.get('severity', ''), "⚪")
                    md_content += f"""**{j}. {severity_emoji} [{issue.get('severity', 'UNKNOWN')}] {issue.get('type', 'Issue')}**

- **Description**: {issue.get('description', 'N/A')}
- **Spec Reference**: `{issue.get('spec_reference', 'N/A')}`
- **Code Location**: `{issue.get('code_location', 'N/A')}`
- **Potential Impact**: {issue.get('potential_impact', 'N/A')}
- **Suggestion**: {issue.get('suggestion', 'N/A')}

"""
            else:
                md_content += "✅ No issues found in this file.\n\n"
            
            md_content += "---\n\n"
        
        md_content += f"""
## Methodology

This report was generated using PRSpec, an Ethereum specification compliance checker.
The analysis was performed using {metadata.analyzer} to compare the implementation
against the official EIP-{metadata.eip_number} specification.

---

*Generated by PRSpec v{metadata.version} | Author: {metadata.author}*
"""
        
        filename = f"prspec_eip{metadata.eip_number}_{metadata.client}_{metadata.timestamp.strftime('%Y%m%d_%H%M%S')}.md"
        filepath = self.output_dir / filename
        
        with open(filepath, 'w') as f:
            f.write(md_content)
        
        return str(filepath)
    
    def _generate_html_report(self, results: List[Dict[str, Any]], 
                              metadata: ReportMetadata) -> str:
        """Generate HTML format report"""
        summary = self._generate_summary(results)
        
        # Severity colors
        severity_colors = {
            "HIGH": "#dc3545",
            "MEDIUM": "#ffc107", 
            "LOW": "#28a745",
        }
        
        status_colors = {
            "FULL_MATCH": "#28a745",
            "PARTIAL_MATCH": "#ffc107",
            "MISSING": "#dc3545",
            "UNCERTAIN": "#6c757d",
            "ERROR": "#dc3545",
        }
        
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{metadata.title}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 3px solid #007bff; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 20px; margin: 20px 0; }}
        .summary-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; }}
        .summary-card .value {{ font-size: 2em; font-weight: bold; color: #007bff; }}
        .summary-card .label {{ color: #666; margin-top: 5px; }}
        .result-card {{ border: 1px solid #ddd; border-radius: 8px; margin: 20px 0; overflow: hidden; }}
        .result-header {{ background: #f8f9fa; padding: 15px 20px; border-bottom: 1px solid #ddd; display: flex; justify-content: space-between; align-items: center; }}
        .result-body {{ padding: 20px; }}
        .status-badge {{ padding: 5px 15px; border-radius: 20px; color: white; font-weight: bold; font-size: 0.9em; }}
        .issue {{ background: #f8f9fa; border-left: 4px solid; padding: 15px; margin: 15px 0; border-radius: 0 8px 8px 0; }}
        .issue-high {{ border-color: #dc3545; }}
        .issue-medium {{ border-color: #ffc107; }}
        .issue-low {{ border-color: #28a745; }}
        .issue-title {{ font-weight: bold; margin-bottom: 10px; }}
        .issue-detail {{ margin: 5px 0; color: #555; }}
        .issue-detail strong {{ color: #333; }}
        code {{ background: #e9ecef; padding: 2px 6px; border-radius: 4px; font-family: monospace; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 {metadata.title}</h1>
        
        <div class="summary-grid">
            <div class="summary-card">
                <div class="value">{summary['overall_status']}</div>
                <div class="label">Overall Status</div>
            </div>
            <div class="summary-card">
                <div class="value">{summary['average_confidence']}%</div>
                <div class="label">Confidence</div>
            </div>
            <div class="summary-card">
                <div class="value">{summary['files_analyzed']}</div>
                <div class="label">Files Analyzed</div>
            </div>
            <div class="summary-card">
                <div class="value" style="color: #dc3545;">{summary['high_severity']}</div>
                <div class="label">High Severity</div>
            </div>
            <div class="summary-card">
                <div class="value" style="color: #ffc107;">{summary['medium_severity']}</div>
                <div class="label">Medium Severity</div>
            </div>
            <div class="summary-card">
                <div class="value" style="color: #28a745;">{summary['low_severity']}</div>
                <div class="label">Low Severity</div>
            </div>
        </div>
        
        <h2>📋 Detailed Findings</h2>
"""
        
        for result in results:
            status = result.get('status', 'UNKNOWN')
            status_color = status_colors.get(status, '#6c757d')
            
            html_content += f"""
        <div class="result-card">
            <div class="result-header">
                <strong>{result.get('file_name', 'Unknown File')}</strong>
                <span class="status-badge" style="background: {status_color};">{status}</span>
            </div>
            <div class="result-body">
                <p><strong>Confidence:</strong> {result.get('confidence', 0)}%</p>
                <p>{result.get('summary', 'No summary available.')}</p>
"""
            
            issues = result.get('issues', [])
            if issues:
                html_content += "<h4>Issues:</h4>"
                for issue in issues:
                    severity = issue.get('severity', 'LOW').lower()
                    html_content += f"""
                <div class="issue issue-{severity}">
                    <div class="issue-title">[{issue.get('severity', 'UNKNOWN')}] {issue.get('type', 'Issue')}</div>
                    <div class="issue-detail"><strong>Description:</strong> {issue.get('description', 'N/A')}</div>
                    <div class="issue-detail"><strong>Spec Reference:</strong> <code>{issue.get('spec_reference', 'N/A')}</code></div>
                    <div class="issue-detail"><strong>Code Location:</strong> <code>{issue.get('code_location', 'N/A')}</code></div>
                    <div class="issue-detail"><strong>Potential Impact:</strong> {issue.get('potential_impact', 'N/A')}</div>
                    <div class="issue-detail"><strong>Suggestion:</strong> {issue.get('suggestion', 'N/A')}</div>
                </div>
"""
            else:
                html_content += "<p>✅ No issues found in this file.</p>"
            
            html_content += """
            </div>
        </div>
"""
        
        html_content += f"""
        <div class="footer">
            <p>Generated by PRSpec v{metadata.version} | Analyzer: {metadata.analyzer}</p>
            <p>EIP-{metadata.eip_number} | Client: {metadata.client} | {metadata.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </div>
</body>
</html>
"""
        
        filename = f"prspec_eip{metadata.eip_number}_{metadata.client}_{metadata.timestamp.strftime('%Y%m%d_%H%M%S')}.html"
        filepath = self.output_dir / filename
        
        with open(filepath, 'w') as f:
            f.write(html_content)
        
        return str(filepath)
    
    def _generate_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary statistics from results"""
        total_issues = 0
        high_severity = 0
        medium_severity = 0
        low_severity = 0
        confidences = []
        statuses = []
        
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
            
            confidences.append(result.get('confidence', 0))
            statuses.append(result.get('status', 'UNKNOWN'))
        
        # Determine overall status
        if 'MISSING' in statuses or high_severity > 0:
            overall_status = "⚠️ ISSUES FOUND"
        elif 'PARTIAL_MATCH' in statuses or medium_severity > 0:
            overall_status = "⚡ PARTIAL"
        elif all(s == 'FULL_MATCH' for s in statuses):
            overall_status = "✅ COMPLIANT"
        else:
            overall_status = "❓ UNCERTAIN"
        
        return {
            "overall_status": overall_status,
            "average_confidence": round(sum(confidences) / len(confidences)) if confidences else 0,
            "files_analyzed": len(results),
            "total_issues": total_issues,
            "high_severity": high_severity,
            "medium_severity": medium_severity,
            "low_severity": low_severity,
        }
    
    def print_summary(self, results: List[Dict[str, Any]], metadata: ReportMetadata):
        """Print a summary to the console using Rich"""
        if not RICH_AVAILABLE:
            print("Rich library not available. Install with: pip install rich")
            return
        
        summary = self._generate_summary(results)
        
        # Create summary table
        table = Table(title=f"📊 {metadata.title}", box=box.ROUNDED)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")
        
        table.add_row("Overall Status", summary['overall_status'])
        table.add_row("Confidence", f"{summary['average_confidence']}%")
        table.add_row("Files Analyzed", str(summary['files_analyzed']))
        table.add_row("Total Issues", str(summary['total_issues']))
        table.add_row("🔴 High Severity", str(summary['high_severity']))
        table.add_row("🟡 Medium Severity", str(summary['medium_severity']))
        table.add_row("🟢 Low Severity", str(summary['low_severity']))
        
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
                    self.console.print(f"  [{color}]● [{severity}][/{color}] {issue.get('description', 'No description')}")
                
                self.console.print()
