#!/usr/bin/env python3
"""Generate screenshot SVGs for README documentation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

def generate_cli_screenshot():
    """Capture the CLI banner + config panel + progress bar + executive summary."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

    console = Console(record=True, width=100)

    # Banner
    BANNER = """[cyan]
  ██████╗ ██████╗ ███████╗██████╗ ███████╗ ██████╗
  ██╔══██╗██╔══██╗██╔════╝██╔══██╗██╔════╝██╔════╝
  ██████╔╝██████╔╝███████╗██████╔╝█████╗  ██║
  ██╔═══╝ ██╔══██╗╚════██║██╔═══╝ ██╔══╝  ██║
  ██║     ██║  ██║███████║██║     ███████╗╚██████╗
  ╚═╝     ╚═╝  ╚═╝╚══════╝╚═╝     ╚══════╝ ╚═════╝
[/cyan]"""
    console.print(BANNER)

    # Config panel
    info_table = Table(show_header=False, box=None, padding=(0, 2))
    info_table.add_column(style="bold white")
    info_table.add_column(style="cyan")
    info_table.add_row("EIP", "1559")
    info_table.add_row("Client", "go-ethereum")
    info_table.add_row("Provider", "gemini")
    info_table.add_row("Output", "html")
    console.print(Panel(info_table, title="[bold]Configuration[/bold]", border_style="blue"))

    # Simulated progress bar (completed)
    console.print()
    console.print("  [green]✓[/green] Analyzing 5 files (~2-5 min (parallel)) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ [green]5/5[/green]")

    # Executive Summary
    summary_text = (
        "PRSpec analysed 5 files from go-ethereum's EIP-1559 implementation using "
        "Gemini (gemini-2.5-pro). Overall verdict: [bold yellow]PARTIAL COMPLIANCE[/bold yellow] "
        "at [bold]87%[/bold] average confidence. 6 issues detected (2 high, 3 medium, 1 low).\n\n"
        "[bold]consensus/misc/eip1559.go[/bold] — FULL_MATCH (0 issues): Base fee calculation correctly "
        "implements the EIP-1559 formula.\n"
        "[bold]core/types/transaction.go[/bold] — PARTIAL_MATCH (2 issues): Transaction type definitions "
        "are correct but missing edge case validations.\n"
        "[bold]core/types/tx_dynamic_fee.go[/bold] — FULL_MATCH (0 issues): DynamicFeeTx struct fully "
        "matches specification.\n"
        "[bold]params/protocol_params.go[/bold] — PARTIAL_MATCH (1 issues): Protocol constants defined "
        "correctly, missing InitialBaseFee bounds.\n"
        "[bold]core/state_transition.go[/bold] — PARTIAL_MATCH (3 issues): Fee burning mechanism implemented "
        "but tip overflow check missing."
    )
    console.print()
    console.print(Panel(summary_text, title="[bold]Executive Summary[/bold]", border_style="blue"))

    # Results table
    console.print()
    results_table = Table(title="EIP-1559 Compliance Report - go-ethereum")
    results_table.add_column("Metric", style="bold white")
    results_table.add_column("Value", style="cyan")
    results_table.add_row("Files Analyzed", "5")
    results_table.add_row("Average Confidence", "87%")
    results_table.add_row("Issues Found", "6")
    results_table.add_row("Full Match", "2 files")
    results_table.add_row("Partial Match", "3 files")
    console.print(results_table)

    console.print("\n  [green]✓ Report saved to:[/green] output/prspec_eip1559_go-ethereum_20260214.html")

    svg = console.export_svg(title="PRSpec v1.3.0 — CLI Analysis")
    Path("docs/cli-analysis.svg").write_text(svg)
    print("    Saved docs/cli-analysis.svg")


def generate_report_overview_screenshot():
    """Generate an HTML-to-SVG of the report header section."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console(record=True, width=100)

    console.print()
    console.print(Panel(
        "[bold cyan]EIP-1559 Compliance Report[/bold cyan]\n"
        "[dim]go-ethereum | 2026-02-14 | Gemini (gemini-2.5-pro) | v1.3.0[/dim]",
        border_style="cyan",
    ))

    # Summary table
    summary = Table(title="Analysis Summary", show_lines=True)
    summary.add_column("File", style="bold")
    summary.add_column("Status", justify="center")
    summary.add_column("Confidence", justify="center")
    summary.add_column("Issues", justify="center")

    summary.add_row("consensus/misc/eip1559.go", "[green]FULL_MATCH[/green]", "95%", "0")
    summary.add_row("core/types/transaction.go", "[yellow]PARTIAL_MATCH[/yellow]", "82%", "2")
    summary.add_row("core/types/tx_dynamic_fee.go", "[green]FULL_MATCH[/green]", "90%", "0")
    summary.add_row("params/protocol_params.go", "[yellow]PARTIAL_MATCH[/yellow]", "85%", "1")
    summary.add_row("core/state_transition.go", "[yellow]PARTIAL_MATCH[/yellow]", "83%", "3")
    console.print(summary)

    # Overall
    console.print()
    console.print(Panel(
        "[bold]Overall: 2/5 files fully compliant | 87% average confidence | 6 issues[/bold]",
        border_style="yellow",
    ))

    svg = console.export_svg(title="PRSpec v1.3.0 — Report Overview")
    Path("docs/report-overview.svg").write_text(svg)
    print("    Saved docs/report-overview.svg")


def generate_findings_screenshot():
    """Generate a detailed findings view."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console(record=True, width=100)

    console.print()
    console.print("[bold cyan]Detailed Findings — core/state_transition.go[/bold cyan]")
    console.print("[dim]Status: PARTIAL_MATCH | Confidence: 83% | 3 issues found[/dim]\n")

    console.print(Panel(
        "The state transition logic correctly implements EIP-1559 fee burning by sending "
        "the base fee portion to a null address. However, the implementation does not "
        "explicitly guard against tip amount overflow when calculating the effective "
        "gas price, and the refund logic for failed transactions could leave residual "
        "base fee amounts unburned.",
        title="[bold]Summary[/bold]",
        border_style="blue",
    ))

    console.print()
    issues = Table(title="Issues", show_lines=True, title_style="bold red")
    issues.add_column("#", style="dim", width=3)
    issues.add_column("Severity", justify="center", width=10)
    issues.add_column("Type", width=18)
    issues.add_column("Description")

    issues.add_row("1", "[red]HIGH[/red]", "MISSING_CHECK",
                   "No overflow protection on tip calculation: "
                   "effectiveTip = gasPrice - baseFee could underflow if "
                   "gasPrice < baseFee due to racing conditions.")
    issues.add_row("2", "[yellow]MEDIUM[/yellow]", "EDGE_CASE",
                   "Failed transaction refund path does not explicitly "
                   "ensure burned base fee is non-recoverable. Spec requires "
                   "base fee to always be burned regardless of tx outcome.")
    issues.add_row("3", "[blue]LOW[/blue]", "SPEC_DEVIATION",
                   "Comment references old EIP draft terminology "
                   "'GASPRICE' instead of current 'effective_gas_price' "
                   "naming convention from the final spec.")
    console.print(issues)

    console.print()
    console.print("[bold green]Suggestion:[/bold green] Add an explicit check: "
                  "[cyan]if gasPrice < baseFee { return ErrUnderpriced }[/cyan] "
                  "before computing the miner tip.")

    svg = console.export_svg(title="PRSpec v1.3.0 — Detailed Findings")
    Path("docs/report-details.svg").write_text(svg)
    print("    Saved docs/report-details.svg")


if __name__ == "__main__":
    Path("docs").mkdir(exist_ok=True)
    print("Generating screenshots...")
    generate_cli_screenshot()
    generate_report_overview_screenshot()
    generate_findings_screenshot()
    print("Done! 3 SVGs saved to docs/")
