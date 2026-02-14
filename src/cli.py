"""Command-line interface for PRSpec."""

import click
from pathlib import Path
from datetime import datetime
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None

from .config import Config
from .analyzer import get_analyzer, GeminiAnalyzer, OpenAIAnalyzer
from .spec_fetcher import SpecFetcher
from .code_fetcher import CodeFetcher
from .parser import CodeParser
from .report_generator import ReportGenerator, ReportMetadata


BANNER = """[cyan]
  ██████╗ ██████╗ ███████╗██████╗ ███████╗ ██████╗
  ██╔══██╗██╔══██╗██╔════╝██╔══██╗██╔════╝██╔════╝
  ██████╔╝██████╔╝███████╗██████╔╝█████╗  ██║
  ██╔═══╝ ██╔══██╗╚════██║██╔═══╝ ██╔══╝  ██║
  ██║     ██║  ██║███████║██║     ███████╗╚██████╗
  ╚═╝     ╚═╝  ╚═╝╚══════╝╚═╝     ╚══════╝ ╚═════╝
[/cyan]"""


@click.group()
@click.version_option(version="1.4.0", prog_name="PRSpec")
def cli():
    """PRSpec — check Ethereum client code against EIP specifications."""
    pass


def _analyze_one_file(analyzer, spec_text, file_path, code_content, context):
    """Analyze a single file — designed to run inside a thread pool."""
    result = analyzer.analyze_compliance(spec_text, code_content, context)
    result_dict = result.to_dict()
    result_dict["file_name"] = file_path
    return result_dict


# ---- Helper: shared analysis pipeline (parallel) ----

def _run_analysis(eip: int, client: str, cfg, llm_provider: str,
                  progress_callback=None):
    """Fetch spec+code, build analyzer, return (results_list, analyzer).
    Runs all file analyses in parallel via threads for speed."""
    spec_fetcher = SpecFetcher(github_token=cfg.github_token)
    code_fetcher = CodeFetcher(github_token=cfg.github_token)

    # --- Fetch specification (generic for any EIP) ---
    spec_data = spec_fetcher.fetch_eip_spec(eip)
    eip_title = spec_data.get("title", f"EIP-{eip}")

    # --- Fetch implementation code (generic for any EIP) ---
    code_files = code_fetcher.fetch_eip_implementation(client, eip)
    language = CodeFetcher.client_language(client)

    # --- Build analyzer ---
    if llm_provider == "gemini":
        analyzer = GeminiAnalyzer(api_key=cfg.gemini_api_key, **cfg.gemini_config)
    else:
        analyzer = OpenAIAnalyzer(api_key=cfg.openai_api_key, **cfg.openai_config)

    # --- Run analysis (parallel) ---
    focus_areas = cfg.get_eip_focus_areas(eip)
    spec_text = spec_data.get("eip_markdown", "")

    futures = {}
    with ThreadPoolExecutor(max_workers=len(code_files)) as pool:
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

    return results, analyzer


@cli.command()
@click.option('--eip', '-e', default=1559, help='EIP number to check (default: 1559)')
@click.option('--client', '-c', default='go-ethereum', help='Client to analyze (default: go-ethereum)')
@click.option('--provider', '-p', default=None, help='LLM provider: gemini or openai')
@click.option('--output', '-o', default='json', help='Output format: json, markdown, html')
@click.option('--config', '-f', default=None, help='Path to config.yaml')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def analyze(eip: int, client: str, provider: Optional[str], output: str, 
            config: Optional[str], verbose: bool):
    """
    Analyze a client implementation against an EIP specification.
    
    Examples:
        prspec analyze --eip 1559 --client go-ethereum --output markdown
        prspec analyze --eip 4844 --client go-ethereum --output html
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
                    progress_callback=on_file_done
                )
        else:
            click.echo(f"\n  Analyzing {n_files} files ({est})...")
            results, analyzer = _run_analysis(eip, client, cfg, llm_provider)
        
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
        else:
            click.echo(f"Error: {str(e)}", err=True)
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
            key = cfg.gemini_api_key
            checks.append(("Gemini API Key", "✓ Set", "green"))
        except ValueError:
            checks.append(("Gemini API Key", "✗ Not set", "red"))
        
        # Check OpenAI API key
        try:
            key = cfg.openai_api_key
            checks.append(("OpenAI API Key", "✓ Set", "green"))
        except ValueError:
            checks.append(("OpenAI API Key", "✗ Not set", "yellow"))
        
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
