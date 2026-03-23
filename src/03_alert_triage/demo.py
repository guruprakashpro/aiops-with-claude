"""
Demo: Alert Triage with Structured Output + Parallel Processing

Run: python src/03_alert_triage/demo.py

Demonstrates:
- JSON mode for guaranteed structured output
- Sequential vs parallel processing time comparison
- Pydantic validation of LLM responses
"""

import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

from src.03_alert_triage.triage import triage_alert, batch_triage_sequential
from src.03_alert_triage.batch_triage import run_parallel_triage, print_triage_comparison

console = Console()

# ---------------------------------------------------------------------------
# 8 sample alerts of varying severity
# ---------------------------------------------------------------------------
SAMPLE_ALERTS = [
    # P1 - Critical
    "CRITICAL: api-gateway error rate 61% in production us-east-1. Users cannot complete purchases. Revenue impact ~$50k/min. Started 12 minutes ago.",

    # P1 - Critical
    "CRITICAL: Database connection pool exhausted (50/50). All write operations failing. Read replicas at 98% capacity. order-processor suspected connection leak.",

    # P2 - Major
    "HIGH: auth-service latency p99=3400ms (SLO: 500ms). Login success rate dropped to 78%. Mobile and web both affected. Started after order-processor deployment.",

    # P2 - Major
    "HIGH: cache-service memory at 87% and rising. Eviction rate 1240 keys/min. If OOM occurs, cache will restart causing cold-start latency spike on all services.",

    # P3 - Minor
    "WARN: Disk usage on logging-server-03 at 78% (threshold: 75%). Current write rate will fill disk in approximately 8 hours. Log rotation not triggering correctly.",

    # P3 - Minor
    "WARN: SSL certificate for api.example.com expires in 14 days. Auto-renewal not yet confirmed. Manual renewal may be required.",

    # P4 - Informational
    "INFO: Scheduled maintenance window for postgres-primary starting in 30 minutes. Expected downtime: 5 minutes for minor version upgrade 14.9 -> 14.12.",

    # P2 - Security
    "HIGH: Unusual login pattern detected - 847 failed login attempts from IP 198.51.100.42 in last 5 minutes targeting admin accounts. Rate limiting partially effective.",
]


def demo_single_triage():
    """Show single alert triage with structured output."""
    console.print(Rule("[bold]Single Alert Triage (JSON Mode)[/bold]"))
    console.print("[dim]Triaging the most critical alert...[/dim]\n")

    alert = SAMPLE_ALERTS[0]
    console.print(Panel(f"[dim]{alert}[/dim]", title="Input Alert", border_style="dim"))

    result = triage_alert(alert)

    severity_colors = {"P1": "red", "P2": "orange3", "P3": "yellow", "P4": "dim"}
    color = severity_colors.get(result.severity, "white")

    console.print(Panel(
        f"[bold]Severity:[/bold] [{color}]{result.severity}[/{color}]\n"
        f"[bold]Category:[/bold] {result.category}\n"
        f"[bold]Summary:[/bold] {result.summary}\n"
        f"[bold]Action:[/bold] {result.suggested_action}\n"
        f"[bold]Escalate:[/bold] {'[red]YES - Page on-call[/red]' if result.escalate_to_human else '[green]No[/green]'}\n"
        f"[bold]ETA:[/bold] {result.estimated_resolution_minutes} minutes\n"
        f"[bold]Runbook:[/bold] {result.runbook_hint or 'N/A'}",
        title="Triage Result (Structured JSON)",
        border_style=color,
    ))


def demo_sequential_vs_parallel():
    """Show the speedup from parallel processing."""
    console.print(Rule("[bold]Sequential vs Parallel: 8 Alerts[/bold]"))

    # Sequential
    console.print("\n[yellow]Step 1: Sequential Processing[/yellow]")
    seq_start = time.time()
    sequential_results = batch_triage_sequential(SAMPLE_ALERTS)
    sequential_time = time.time() - seq_start
    console.print(f"[yellow]Sequential complete: {sequential_time:.2f}s[/yellow]\n")

    # Parallel
    console.print("[green]Step 2: Parallel Processing (asyncio.gather)[/green]")
    parallel_results, parallel_time = run_parallel_triage(SAMPLE_ALERTS)
    console.print(f"[green]Parallel complete: {parallel_time:.2f}s[/green]\n")

    # Comparison
    print_triage_comparison(
        sequential_results, sequential_time,
        parallel_results, parallel_time,
    )


def main():
    console.print()
    console.print(Panel(
        "[bold green]Module 03: Alert Triage[/bold green]\n"
        "[dim]Optimizations: Structured Output (JSON Mode) + Parallel Processing[/dim]",
        expand=False,
        border_style="green",
    ))

    console.print(Panel(
        "[bold]Why JSON Mode?[/bold]\n"
        "• Guaranteed valid JSON output from the LLM\n"
        "• No regex fragility for parsing severity, booleans, integers\n"
        "• Pydantic validates all fields - fail fast on bad data\n"
        "• Downstream code gets typed objects, not strings\n\n"
        "[bold]Why Parallel?[/bold]\n"
        "• Each API call is I/O bound (waiting for network)\n"
        "• asyncio.gather() runs all requests simultaneously\n"
        "• 8 alerts in parallel ≈ time of 1 alert",
        title="Optimizations Explained",
        border_style="blue",
        expand=False,
    ))

    try:
        demo_single_triage()
    except Exception as e:
        console.print(f"[red]Single triage error: {e}[/red]")

    console.print()

    try:
        demo_sequential_vs_parallel()
    except Exception as e:
        console.print(f"[red]Batch triage error: {e}[/red]")

    console.print()
    console.print(Panel(
        "[bold green]Module 03 Complete[/bold green]\n\n"
        "Optimizations used:\n"
        "  [cyan]STRUCTURED OUTPUT[/cyan]   - json_mode=True, Pydantic validation\n"
        "  [cyan]PARALLEL PROCESSING[/cyan] - asyncio.gather() for concurrent requests",
        expand=False,
        border_style="green",
    ))


if __name__ == "__main__":
    main()
