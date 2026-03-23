"""
Demo: Full AIops Multi-Agent Pipeline

Run: python src/06_multi_agent_pipeline/demo.py

Demonstrates:
- End-to-end pipeline chaining all modules
- Orchestration of anomaly detection → triage → RCA → runbook
- Rich stage-by-stage output with panels
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

from src.01_log_analysis.sample_data import SAMPLE_LOGS, SAMPLE_METRICS
from src.06_multi_agent_pipeline.orchestrator import AIOpsPipeline, IncidentReport

console = Console()


def print_incident_report(report: IncidentReport) -> None:
    """Print a complete incident report with Rich formatting."""

    severity_colors = {"P1": "red", "P2": "orange3", "P3": "yellow", "P4": "green"}
    color = severity_colors.get(report.severity, "white")

    # Header
    console.print(Panel(
        f"[bold white]INCIDENT REPORT[/bold white]\n"
        f"ID: [bold]{report.incident_id}[/bold]  "
        f"Severity: [{color}]{report.severity}[/{color}]  "
        f"Time: {report.timestamp[:19]}",
        border_style=color,
        expand=True,
    ))

    # Root cause
    console.print(Panel(
        f"[bold white]{report.root_cause}[/bold white]\n\n"
        f"[dim]Confidence: {report.rca_confidence:.0%} | "
        f"Deployment-related: {'Yes' if report.deployment_related else 'No'}[/dim]",
        title="[bold red]Root Cause[/bold red]",
        border_style="red",
    ))

    # Two-column details
    details_table = Table(box=box.ROUNDED, show_header=False, padding=(0, 1))
    details_table.add_column("Field", style="bold cyan", width=22)
    details_table.add_column("Value")

    details_table.add_row(
        "Affected Services",
        ", ".join(f"[yellow]{s}[/yellow]" for s in report.affected_services),
    )
    details_table.add_row("Resolution Estimate", report.resolution_time_estimate)
    details_table.add_row(
        "Anomalies Detected",
        str(len(report.anomalies)),
    )
    details_table.add_row(
        "Pipeline Duration",
        f"{report.pipeline_duration_seconds:.1f}s",
    )

    console.print(details_table)

    # Anomalies list
    if report.anomalies:
        console.print(f"\n[bold red]Anomalies ({len(report.anomalies)}):[/bold red]")
        for a in report.anomalies[:6]:
            console.print(f"  [red]•[/red] {a[:120]}")
        if len(report.anomalies) > 6:
            console.print(f"  [dim]... and {len(report.anomalies) - 6} more[/dim]")

    # Runbook steps
    if report.runbook_steps:
        console.print(f"\n[bold green]Key Runbook Steps:[/bold green]")
        for i, step in enumerate(report.runbook_steps[:6], 1):
            console.print(f"  [green]{i}.[/green] {step[:110]}")

    # Actions taken
    console.print(f"\n[bold blue]Pipeline Actions Taken:[/bold blue]")
    for action in report.actions_taken:
        console.print(f"  [blue]✓[/blue] {action}")


def main():
    console.print()
    console.print(Panel(
        "[bold green]Module 06: Multi-Agent Pipeline[/bold green]\n"
        "[dim]Full end-to-end AIops pipeline combining all optimization modules[/dim]",
        expand=False,
        border_style="green",
    ))

    # Show pipeline architecture
    console.print(Panel(
        "[bold]Pipeline Architecture:[/bold]\n\n"
        "  [cyan]Logs + Metrics[/cyan]\n"
        "       ↓\n"
        "  [cyan]Stage 1:[/cyan] Anomaly Detection  [dim](streaming + model selection)[/dim]\n"
        "       ↓ (if anomaly found)\n"
        "  [cyan]Stage 2:[/cyan] Alert Triage        [dim](structured output / JSON mode)[/dim]\n"
        "       ↓ (if P1 or P2)\n"
        "  [cyan]Stage 3:[/cyan] RCA Investigation   [dim](tool use agentic loop)[/dim]\n"
        "       ↓\n"
        "  [cyan]Stage 4:[/cyan] Runbook Generation  [dim](prompt caching)[/dim]\n"
        "       ↓\n"
        "  [cyan]Stage 5:[/cyan] Incident Report     [dim](full structured output)[/dim]",
        title="Architecture",
        border_style="blue",
        expand=False,
    ))

    # -----------------------------------------------------------------------
    # Run the pipeline with sample production incident data
    # -----------------------------------------------------------------------
    console.print(Rule("[bold]Running Pipeline: Production Database Incident[/bold]"))
    console.print("[dim]Using sample logs and metrics from Module 01...[/dim]\n")

    pipeline = AIOpsPipeline(verbose=True)

    try:
        report = pipeline.run(SAMPLE_LOGS, SAMPLE_METRICS)

        console.print()
        console.print(Rule("[bold]Pipeline Complete - Incident Report[/bold]"))
        print_incident_report(report)

    except Exception as e:
        console.print(f"[red]Pipeline error: {e}[/red]")
        import traceback
        traceback.print_exc()
        return

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    console.print()
    summary_table = Table(
        box=box.ROUNDED,
        title="Pipeline Optimization Summary",
        header_style="bold cyan",
    )
    summary_table.add_column("Stage", style="bold")
    summary_table.add_column("Module")
    summary_table.add_column("Optimization Used")

    summary_table.add_row("Anomaly Detection", "01 + 05", "Streaming, Model Selection, Multi-Turn")
    summary_table.add_row("Alert Triage", "03", "JSON Mode, Structured Output")
    summary_table.add_row("RCA Investigation", "02", "Tool Use, Agentic Loop")
    summary_table.add_row("Runbook Generation", "04", "Prompt Caching, Result Caching")
    summary_table.add_row("Report Compilation", "06", "Pydantic Validation, Full Pipeline")

    console.print(summary_table)

    console.print()
    console.print(Panel(
        "[bold green]Module 06 Complete[/bold green]\n\n"
        "This pipeline demonstrates all 7 optimization techniques working together:\n"
        "  [cyan]1.[/cyan] Streaming          [cyan]2.[/cyan] Model Selection    [cyan]3.[/cyan] Tool Use\n"
        "  [cyan]4.[/cyan] Structured Output  [cyan]5.[/cyan] Parallel Processing [cyan]6.[/cyan] Prompt Caching\n"
        "  [cyan]7.[/cyan] Multi-Turn Context",
        expand=False,
        border_style="green",
    ))


if __name__ == "__main__":
    main()
