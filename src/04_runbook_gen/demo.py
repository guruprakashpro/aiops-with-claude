"""
Demo: Runbook Generation with Prompt Caching Simulation

Run: python src/04_runbook_gen/demo.py

Demonstrates:
- Prompt caching simulation (reusing large system context)
- Token comparison: rich context vs minimal prompt
- Application-level result caching to avoid redundant API calls
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich.syntax import Syntax
from rich import box

from src.04_runbook_gen.generator import (
    generate_runbook,
    generate_runbook_minimal,
    get_cache_stats,
    CACHED_CONTEXT_TOKENS,
)

console = Console()

INCIDENT_TYPES = [
    {
        "type": "Database connection pool exhausted",
        "context": "HikariCP connection pool, PostgreSQL 14, order-processor service suspected of connection leak",
    },
    {
        "type": "High memory usage on application pods",
        "context": "Kubernetes deployment, memory at 87-92%, OOM kills starting in cache-service",
    },
    {
        "type": "API gateway 5xx error spike",
        "context": "Error rate 61%, upstream services timing out, load balancer still healthy",
    },
]


def main():
    console.print()
    console.print(Panel(
        "[bold green]Module 04: Runbook Generation[/bold green]\n"
        "[dim]Optimizations: Prompt Caching Simulation + Token Optimization[/dim]",
        expand=False,
        border_style="green",
    ))

    console.print(Panel(
        "[bold]How Prompt Caching Works:[/bold]\n\n"
        "• Build a rich system context ONCE (template + standards + commands)\n"
        "• Send it with every request as the system prompt\n"
        "• APIs with caching (Anthropic Claude) skip reprocessing this prefix\n"
        "• Result: pay full price for first call, ~10% for subsequent calls\n\n"
        "[bold]Application-Level Caching:[/bold]\n"
        "• Store generated runbooks in memory\n"
        "• Identical requests return cached result instantly (0 API calls)",
        title="Caching Strategy",
        border_style="blue",
        expand=False,
    ))

    console.print(f"\n[dim]Cached system context size: ~{int(CACHED_CONTEXT_TOKENS):,} tokens (simulated)[/dim]\n")

    results = []

    # -----------------------------------------------------------------------
    # Generate runbooks with rich context
    # -----------------------------------------------------------------------
    console.print(Rule("[bold]Generating Runbooks (Rich Context)[/bold]"))

    for i, incident in enumerate(INCIDENT_TYPES, 1):
        console.print(f"\n[bold cyan]{i}. {incident['type']}[/bold cyan]")

        try:
            result = generate_runbook(incident["type"], incident["context"])
            results.append(result)

            status = "[green](from cache)[/green]" if result["from_cache"] else f"[dim]{result['generation_time']:.1f}s[/dim]"
            console.print(f"   Status: {status} | Tokens: {result['tokens_used']} | Prompt: {result['prompt_tokens']}")

            # Show first 20 lines of the runbook
            preview_lines = result["runbook"].split("\n")[:20]
            preview = "\n".join(preview_lines) + "\n[dim]... (truncated)[/dim]"
            console.print(Panel(preview, title=f"Runbook Preview: {incident['type'][:40]}", border_style="dim"))

        except Exception as e:
            console.print(f"   [red]Error: {e}[/red]")
            results.append({"tokens_used": 0, "prompt_tokens": 0, "generation_time": 0, "from_cache": False})

    # -----------------------------------------------------------------------
    # Cache hit demo: request the same runbook again
    # -----------------------------------------------------------------------
    console.print(Rule("[bold]Cache Hit Demo[/bold]"))
    console.print("[dim]Requesting the same runbook a second time...[/dim]")

    try:
        cached_result = generate_runbook(INCIDENT_TYPES[0]["type"])
        if cached_result["from_cache"]:
            console.print("[green]Cache HIT - returned instantly, 0 API tokens used![/green]")
        else:
            console.print("[yellow]Cache MISS - generated fresh[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

    # -----------------------------------------------------------------------
    # Token comparison: rich context vs minimal prompt
    # -----------------------------------------------------------------------
    console.print(Rule("[bold]Token Optimization: Rich vs Minimal Prompt[/bold]"))
    console.print("[dim]Comparing token usage and output quality...[/dim]\n")

    test_incident = "API gateway 5xx error spike"

    try:
        rich_result = generate_runbook(test_incident)

        minimal_result = generate_runbook_minimal(test_incident)

        comparison_table = Table(box=box.ROUNDED, title="Prompt Strategy Comparison")
        comparison_table.add_column("Metric", style="bold cyan")
        comparison_table.add_column("Rich Context (Cached)", justify="right")
        comparison_table.add_column("Minimal Prompt", justify="right")
        comparison_table.add_column("Difference", justify="right")

        rich_prompt = rich_result.get("prompt_tokens", 0)
        minimal_prompt = minimal_result.get("prompt_tokens", 0)
        rich_total = rich_result.get("tokens_used", 0)
        minimal_total = minimal_result.get("tokens_used", 0)
        rich_completion = rich_total - rich_prompt
        minimal_completion = minimal_total - minimal_prompt

        comparison_table.add_row(
            "Prompt Tokens",
            f"{rich_prompt:,}",
            f"{minimal_prompt:,}",
            f"[yellow]+{rich_prompt - minimal_prompt:,}[/yellow]" if rich_prompt > minimal_prompt else f"[green]{rich_prompt - minimal_prompt:,}[/green]",
        )
        comparison_table.add_row(
            "Completion Tokens",
            f"{rich_completion:,}",
            f"{minimal_completion:,}",
            f"[green]+{rich_completion - minimal_completion:,}[/green]" if rich_completion > minimal_completion else f"[yellow]{rich_completion - minimal_completion:,}[/yellow]",
        )
        comparison_table.add_row(
            "Total Tokens",
            f"{rich_total:,}",
            f"{minimal_total:,}",
            f"{rich_total - minimal_total:+,}",
        )
        comparison_table.add_row(
            "Generation Time",
            f"{rich_result.get('generation_time', 0):.1f}s",
            f"{minimal_result.get('generation_time', 0):.1f}s",
            "",
        )
        comparison_table.add_row(
            "Output Quality",
            "[green]Structured, complete[/green]",
            "[yellow]Variable, may miss sections[/yellow]",
            "",
        )

        console.print(comparison_table)

        console.print(Panel(
            "[bold]Key Insight:[/bold]\n"
            "Rich context uses more prompt tokens, BUT:\n"
            "• With true prompt caching, cached prefix tokens cost ~10% of uncached\n"
            "• The output is consistently structured and complete\n"
            "• No need to repeat formatting instructions in every request\n"
            "• For N runbook requests: [green]savings = (N-1) * cached_token_cost * 0.9[/green]",
            border_style="blue",
        ))
    except Exception as e:
        console.print(f"[red]Token comparison error: {e}[/red]")

    # -----------------------------------------------------------------------
    # Cache statistics
    # -----------------------------------------------------------------------
    console.print(Rule("[bold]Cache Statistics[/bold]"))
    stats = get_cache_stats()
    stats_table = Table(box=box.SIMPLE, show_header=False)
    stats_table.add_column("Metric", style="bold cyan")
    stats_table.add_column("Value")

    for k, v in stats.items():
        stats_table.add_row(k.replace("_", " ").title(), str(v))

    console.print(stats_table)

    console.print()
    console.print(Panel(
        "[bold green]Module 04 Complete[/bold green]\n\n"
        "Optimizations used:\n"
        "  [cyan]PROMPT CACHING[/cyan]   - Reuse large context across requests\n"
        "  [cyan]TOKEN OPTIMIZATION[/cyan] - Rich context > minimal for quality\n"
        "  [cyan]RESULT CACHING[/cyan]   - Skip API for identical requests",
        expand=False,
        border_style="green",
    ))


if __name__ == "__main__":
    main()
