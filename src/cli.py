"""Command-line interface for PRSpec."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional

import click

from src import __version__

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn
    from rich.table import Table
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None

from .analyzer import AzureAIAnalyzer, GeminiAnalyzer, OpenAIAnalyzer
from .code_fetcher import CodeFetcher
from .config import Config
from .report_generator import ReportGenerator, ReportMetadata
from .spec_fetcher import SpecFetcher

BANNER = """[cyan]
  ██████╗ ██████╗ ███████╗██████╗ ███████╗ ██████╗
  ██╔══██╗██╔══██╗██╔════╝██╔══██╗██╔════╝██╔════╝
  ██████╔╝██████╔╝███████╗██████╔╝█████╗  ██║
  ██╔═══╝ ██╔══██╗╚════██║██╔═══╝ ██╔══╝  ██║
  ██║     ██║  ██║███████║██║     ███████╗╚██████╗
  ╚═╝     ╚═╝  ╚═╝╚══════╝╚═╝     ╚══════╝ ╚═════╝
[/cyan]"""


@click.group()
@click.version_option(version=__version__, prog_name="PRSpec")
def cli():
    """PRSpec — check Ethereum client code against EIP specifications."""
    pass


def _analyze_one_file(analyzer, spec_text, file_path, code_content, context):
    """Analyze a single file — designed to run inside a thread pool."""
    result = analyzer.analyze_compliance(spec_text, code_content, context)
    result_dict = result.to_dict()
    result_dict["file_name"] = file_path
    return result_dict


def _build_analyzer(llm_provider, cfg):
    """Construct the analyzer for the active provider."""
    if llm_provider == "gemini":
        return GeminiAnalyzer(api_key=cfg.gemini_api_key, **cfg.gemini_config)
    if llm_provider == "azure":
        return AzureAIAnalyzer(api_key=cfg.azure_api_key, **cfg.azure_config)
    return OpenAIAnalyzer(api_key=cfg.openai_api_key, **cfg.openai_config)


def _build_verify_analyzer(llm_provider, cfg, primary):
    """Pick the analyzer for the skeptic rounds.

    Azure can point verification at a separate (typically cheaper) deployment
    via ``AZURE_AI_VERIFY_DEPLOYMENT`` — e.g. Opus for the primary pass and
    Sonnet for the rounds.  Every other case reuses the primary analyzer.
    """
    if llm_provider == "azure":
        verify_cfg = cfg.azure_verify_config
        if verify_cfg:
            return AzureAIAnalyzer(api_key=cfg.azure_api_key, **verify_cfg)
    return primary


# ---- Helper: shared analysis pipeline (parallel) ----

def _run_analysis(eip: int, client: str, cfg, llm_provider: str,
                  progress_callback=None, verify: bool = False,
                  verify_rounds: int = 2):
    """Fetch spec+code, build analyzer, return (results_list, analyzer).
    Runs all file analyses in parallel via threads for speed.  When *verify*
    is set, each candidate finding is then cross-examined and grounded."""
    spec_fetcher = SpecFetcher(github_token=cfg.github_token)
    code_fetcher = CodeFetcher(github_token=cfg.github_token)

    # --- Fetch specification (generic for any EIP) ---
    # Prefer the focused fork-to-fork diff; falls back to the full spec file.
    spec_data = spec_fetcher.fetch_eip_spec(eip, mode="diff")
    eip_title = spec_data.get("title", f"EIP-{eip}")

    # --- Fetch implementation code (generic for any EIP) ---
    code_files = code_fetcher.fetch_eip_implementation(client, eip)
    language = CodeFetcher.client_language(client)

    # --- Build analyzer ---
    analyzer = _build_analyzer(llm_provider, cfg)

    # --- Assemble spec text (EIP prose + reference-impl fork diff) ---
    focus_areas = cfg.get_eip_focus_areas(eip)
    spec_text = spec_data.get("eip_markdown", "")
    exec_spec = spec_data.get("execution_spec")
    if exec_spec and spec_data.get("execution_spec_mode") == "diff":
        spec_text = (
            f"{spec_text}\n\n"
            f"=== EXECUTION-SPEC FORK DIFF ({spec_data.get('title', eip)}) ===\n"
            f"{exec_spec}"
        )

    # --- Run analysis (parallel) ---
    futures = {}
    with ThreadPoolExecutor(max_workers=min(len(code_files), 5)) as pool:
        for file_path, code_content in code_files.items():
            context = {
                "eip_number": eip,
                "eip_title": eip_title,
                "file_name": file_path,
                "function_name": f"EIP-{eip} implementation",
                "language": language,
                "focus_areas": focus_areas,
            }
            future = pool.submit(
                _analyze_one_file, analyzer, spec_text,
                file_path, code_content, context
            )
            futures[future] = file_path

        results = []
        for future in as_completed(futures):
            results.append(future.result())
            if progress_callback:
                progress_callback(futures[future])

    # Keep original file order
    file_order = list(code_files.keys())
    results.sort(key=lambda r: file_order.index(r["file_name"]))

    # --- Adversarial verification (optional) ---
    if verify:
        from .verifier import VerificationEngine
        verify_analyzer = _build_verify_analyzer(llm_provider, cfg, analyzer)
        engine = VerificationEngine(verify_analyzer, rounds=verify_rounds)
        base_context = {
            "eip_number": eip,
            "eip_title": eip_title,
            "language": language,
            "focus_areas": focus_areas,
        }
        engine.verify_results(results, spec_text, code_files, base_context)

    return results, analyzer


@cli.command()
@click.option('--eip', '-e', default=1559, help='EIP number to check (default: 1559)')
@click.option('--client', '-c', default='go-ethereum', help='Client to analyze (default: go-ethereum)')
@click.option('--provider', '-p', default=None, help='LLM provider: gemini, openai, or azure')
@click.option('--output', '-o', default='json', help='Output format: json, markdown, html')
@click.option('--config', '-f', default=None, help='Path to config.yaml')
@click.option('--verify/--no-verify', default=True,
              help='Cross-examine each finding and grade it (extra API calls)')
@click.option('--verify-rounds', default=2, show_default=True,
              help='Independent skeptic passes per finding')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def analyze(eip: int, client: str, provider: Optional[str], output: str,
            config: Optional[str], verify: bool, verify_rounds: int,
            verbose: bool):
    """
    Analyze a client implementation against an EIP specification.

    Examples:
        prspec analyze --eip 1559 --client go-ethereum --output markdown
        prspec analyze --eip 4844 --client go-ethereum --output html
        prspec analyze --eip 1559 --client nethermind --verify
    """
    try:
        # Load configuration
        cfg = Config(config)
        llm_provider = provider if provider else cfg.llm_provider

        # Banner + config summary
        if RICH_AVAILABLE:
            console.print(BANNER)
            info_table = Table(show_header=False, box=None, padding=(0, 2))
            info_table.add_column(style="bold white")
            info_table.add_column(style="cyan")
            info_table.add_row("EIP", str(eip))
            info_table.add_row("Client", client)
            info_table.add_row("Provider", llm_provider)
            info_table.add_row("Output", output)
            info_table.add_row("Verify", f"on · {verify_rounds} rounds" if verify else "off")
            console.print(Panel(info_table, title="[bold]Configuration[/bold]", border_style="blue"))
        else:
            click.echo("\n  PRSpec - Ethereum Specification Compliance Checker\n")
            click.echo(f"  EIP: {eip}  |  Client: {client}  |  Provider: {llm_provider}")

        # Get file count for time estimate
        n_files = len(CodeFetcher.CLIENTS.get(client, {}).get("eip_files", {}).get(eip, []))
        est = f"~{max(1, n_files // 2)}-{n_files} min (parallel)" if n_files > 1 else "~1-2 min"

        if RICH_AVAILABLE:
            console.print()
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(bar_width=30),
                MofNCompleteColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(
                    f"Analyzing {n_files} files ({est})", total=n_files
                )
                def on_file_done(fname):
                    progress.advance(task)
                results, analyzer = _run_analysis(
                    eip, client, cfg, llm_provider,
                    progress_callback=on_file_done,
                    verify=verify, verify_rounds=verify_rounds,
                )
            if verify:
                n_found = sum(len(r.get("issues", [])) for r in results)
                console.print(
                    f"[dim]Verified {n_found} candidate finding(s) "
                    f"across {verify_rounds} skeptic round(s).[/dim]"
                )
        else:
            click.echo(f"\n  Analyzing {n_files} files ({est})...")
            results, analyzer = _run_analysis(
                eip, client, cfg, llm_provider,
                verify=verify, verify_rounds=verify_rounds,
            )

        # Generate report
        report_gen = ReportGenerator(cfg.output_config.get("directory", "output"))
        metadata = ReportMetadata(
            title=f"EIP-{eip} Compliance Report - {client}",
            eip_number=eip,
            client=client,
            timestamp=datetime.now(),
            analyzer=f"{llm_provider.capitalize()} ({analyzer.get_model_info()['model']})"
        )

        report_path = report_gen.generate_report(results, metadata, output)

        # Print summary
        if RICH_AVAILABLE:
            report_gen.print_summary(results, metadata)
            console.print(f"\n[green]✓ Report saved to:[/green] {report_path}")
        else:
            click.echo(f"\nReport saved to: {report_path}")

    except Exception as e:
        if RICH_AVAILABLE:
            console.print(f"[red]Error:[/red] {str(e)}")
            if verbose:
                import traceback
                console.print(f"[dim]{traceback.format_exc()}[/dim]")
        else:
            click.echo(f"Error: {str(e)}", err=True)
            if verbose:
                import traceback
                click.echo(traceback.format_exc(), err=True)
        raise click.Abort()


@cli.command()
@click.option('--eip', '-e', default=1559, help='EIP number to check (default: 1559)')
@click.option('--clients', '-c', default=None,
              help='Comma-separated clients (default: all with mappings for the EIP)')
@click.option('--provider', '-p', default=None, help='LLM provider: gemini, openai, or azure')
@click.option('--output', '-o', default='html', help='Output format: json, markdown, html')
@click.option('--config', '-f', default=None, help='Path to config.yaml')
@click.option('--llm-synthesis/--no-llm-synthesis', default=False,
              help='Add an LLM-generated divergence narrative (extra API call)')
@click.option('--verify/--no-verify', default=False,
              help='Verify each finding before comparing (extra API calls per client)')
@click.option('--verify-rounds', default=2, show_default=True,
              help='Independent skeptic passes per finding')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def diff(eip: int, clients: Optional[str], provider: Optional[str], output: str,
         config: Optional[str], llm_synthesis: bool, verify: bool,
         verify_rounds: int, verbose: bool):
    """
    Cross-client differential: compare how multiple clients implement one EIP.

    Examples:
        prspec diff --eip 1559
        prspec diff --eip 4844 --clients go-ethereum,nethermind,besu --output html
    """
    from .differential import ClientAnalysis, DifferentialEngine

    try:
        cfg = Config(config)
        llm_provider = provider if provider else cfg.llm_provider

        # Resolve the client list: explicit, or every client that maps this EIP.
        if clients:
            client_list = [c.strip() for c in clients.split(',') if c.strip()]
        else:
            client_list = [
                c for c in CodeFetcher.supported_clients()
                if eip in CodeFetcher.supported_eips_for_client(c)
            ]

        # Keep only clients that actually have file mappings for this EIP.
        usable = [
            c for c in client_list
            if eip in CodeFetcher.supported_eips_for_client(c)
        ]
        skipped = [c for c in client_list if c not in usable]

        if len(usable) < 2:
            raise click.ClickException(
                f"Differential needs at least 2 clients with EIP-{eip} mappings. "
                f"Usable: {usable or 'none'}."
            )

        if RICH_AVAILABLE:
            console.print(BANNER)
            info_table = Table(show_header=False, box=None, padding=(0, 2))
            info_table.add_column(style="bold white")
            info_table.add_column(style="cyan")
            info_table.add_row("EIP", str(eip))
            info_table.add_row("Clients", ", ".join(usable))
            info_table.add_row("Provider", llm_provider)
            info_table.add_row("Output", output)
            if skipped:
                info_table.add_row("Skipped", ", ".join(skipped))
            console.print(Panel(info_table, title="[bold]Differential[/bold]", border_style="blue"))
        else:
            click.echo(f"\n  PRSpec differential — EIP-{eip} across {', '.join(usable)}\n")

        # Analyze each client through the standard pipeline.
        per_client = {}
        last_analyzer = None
        for client in usable:
            if RICH_AVAILABLE:
                console.print(f"[dim]Analyzing {client}...[/dim]")
            results, analyzer = _run_analysis(
                eip, client, cfg, llm_provider,
                verify=verify, verify_rounds=verify_rounds,
            )
            per_client[client] = ClientAnalysis(
                client=client,
                language=CodeFetcher.client_language(client),
                results=results,
            )
            last_analyzer = analyzer

        # Build the differential.
        engine = DifferentialEngine(focus_areas=cfg.get_eip_focus_areas(eip))
        eip_title = SpecFetcher.get_eip_title(eip)
        differential = engine.build(per_client, eip, eip_title, confirmed_only=verify)

        if llm_synthesis and last_analyzer is not None:
            differential.llm_synthesis = engine.synthesize(
                last_analyzer, differential, per_client
            )

        # Report.
        report_gen = ReportGenerator(cfg.output_config.get("directory", "output"))
        report_path = report_gen.generate_differential_report(differential, output)

        if RICH_AVAILABLE:
            report_gen.print_differential_summary(differential)
            console.print(f"\n[green]✓ Differential report saved to:[/green] {report_path}")
        else:
            click.echo(differential.narrative)
            click.echo(f"\nReport saved to: {report_path}")

    except click.ClickException:
        raise
    except Exception as e:
        if RICH_AVAILABLE:
            console.print(f"[red]Error:[/red] {str(e)}")
            if verbose:
                import traceback
                console.print(f"[dim]{traceback.format_exc()}[/dim]")
        else:
            click.echo(f"Error: {str(e)}", err=True)
            if verbose:
                import traceback
                click.echo(traceback.format_exc(), err=True)
        raise click.Abort()


@cli.command()
@click.option('--eip', '-e', default=1559, help='EIP number to fetch')
def fetch_spec(eip: int):
    """
    Fetch and display an EIP specification.

    Example:
        prspec fetch-spec --eip 1559
        prspec fetch-spec --eip 4844
    """
    try:
        spec_fetcher = SpecFetcher()
        content = spec_fetcher.fetch_eip(eip)

        if RICH_AVAILABLE:
            from rich.markdown import Markdown
            console.print(Markdown(content[:5000] + "...\n\n[Truncated]"))
        else:
            click.echo(content[:5000])
            click.echo("\n...[Truncated]")

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)


@cli.command()
@click.option('--client', '-c', default='go-ethereum', help='Client to list files from')
@click.option('--eip', '-e', default=1559, help='EIP to find related files')
def list_files(client: str, eip: int):
    """
    List implementation files for an EIP in a client.

    Example:
        prspec list-files --client go-ethereum --eip 1559
        prspec list-files --client go-ethereum --eip 4844
    """
    try:
        code_fetcher = CodeFetcher()
        files = code_fetcher.fetch_eip_implementation(client, eip)

        if RICH_AVAILABLE:
            from rich.table import Table
            table = Table(title=f"EIP-{eip} Files in {client}")
            table.add_column("File Path", style="cyan")
            table.add_column("Lines", style="green")

            for path, content in files.items():
                lines = len(content.split('\n'))
                table.add_row(path, str(lines))

            console.print(table)
        else:
            click.echo(f"EIP-{eip} files in {client}:")
            for path, content in files.items():
                click.echo(f"  - {path} ({len(content.split(chr(10)))} lines)")

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)


@cli.command()
def list_eips():
    """List all supported EIPs with full file mappings."""
    try:
        spec_fetcher = SpecFetcher()
        code_fetcher = CodeFetcher()

        if RICH_AVAILABLE:
            from rich.table import Table
            table = Table(title="Supported EIPs")
            table.add_column("EIP", style="cyan")
            table.add_column("Title", style="white")
            table.add_column("Clients with mappings", style="green")

            for eip_num in spec_fetcher.supported_eips():
                title = spec_fetcher.get_eip_title(eip_num)
                clients_with = [
                    c for c in code_fetcher.supported_clients()
                    if eip_num in code_fetcher.supported_eips_for_client(c)
                ]
                table.add_row(str(eip_num), title, ", ".join(clients_with) or "—")

            console.print(table)
        else:
            click.echo("Supported EIPs:")
            for eip_num in spec_fetcher.supported_eips():
                title = spec_fetcher.get_eip_title(eip_num)
                click.echo(f"  EIP-{eip_num}: {title}")

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)


@cli.command()
def clear_cache():
    """Clear all cached specifications and code files."""
    try:
        spec_fetcher = SpecFetcher()
        code_fetcher = CodeFetcher()

        spec_fetcher.clear_cache()
        code_fetcher.clear_cache()

        if RICH_AVAILABLE:
            console.print("[green]✓ Cache cleared successfully[/green]")
        else:
            click.echo("Cache cleared successfully")

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)


@cli.command()
def check_config():
    """Verify configuration and API keys."""
    try:
        cfg = Config()

        checks = []

        # Check Gemini API key
        try:
            _ = cfg.gemini_api_key
            checks.append(("Gemini API Key", "✓ Set", "green"))
        except ValueError:
            checks.append(("Gemini API Key", "✗ Not set", "red"))

        # Check OpenAI API key
        try:
            _ = cfg.openai_api_key
            checks.append(("OpenAI API Key", "✓ Set", "green"))
        except ValueError:
            checks.append(("OpenAI API Key", "✗ Not set", "yellow"))

        # Check Azure AI Foundry key + endpoint
        try:
            _ = cfg.azure_api_key
            endpoint = cfg.azure_config.get("endpoint")
            if endpoint:
                checks.append(("Azure AI Key", "✓ Set", "green"))
            else:
                checks.append(("Azure AI Key", "✓ Set (endpoint missing)", "yellow"))
        except ValueError:
            checks.append(("Azure AI Key", "✗ Not set", "yellow"))

        # Check GitHub token
        token = cfg.github_token
        if token:
            checks.append(("GitHub Token", "✓ Set", "green"))
        else:
            checks.append(("GitHub Token", "○ Optional, not set", "yellow"))

        # Check provider
        checks.append(("Active Provider", cfg.llm_provider, "cyan"))

        if RICH_AVAILABLE:
            from rich.table import Table
            table = Table(title="Configuration Status")
            table.add_column("Setting", style="white")
            table.add_column("Status", style="white")

            for name, status, color in checks:
                table.add_row(name, f"[{color}]{status}[/{color}]")

            console.print(table)
        else:
            click.echo("Configuration Status:")
            for name, status, _ in checks:
                click.echo(f"  {name}: {status}")

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)


def main():
    """Main entry point"""
    cli()


if __name__ == "__main__":
    main()
