"""
Demo: Log Analysis with Streaming + Model Selection

Run: python src/01_log_analysis/demo.py

Demonstrates:
- Real-time streaming output for log analysis
- Model selection (FAST vs SMART)
- Metric anomaly detection
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich import box

from src.01_log_analysis.sample_data import SAMPLE_LOGS, SAMPLE_METRICS
from src.01_log_analysis.analyzer import (
    analyze_logs_streaming,
    analyze_metrics,
    detect_anomalies,
)
from src.llm_client import LLMClient

console = Console()


def main():
    console.print()
    console.print(Panel(
        "[bold green]Module 01: Log Analysis[/bold green]\n"
        "[dim]Optimizations: Streaming + Model Selection[/dim]",
        expand=False,
        border_style="green",
    ))

    # -----------------------------------------------------------------------
    # Step 1: Show sample logs
    # -----------------------------------------------------------------------
    console.print(Rule("[bold]Sample Logs (last 25 minutes)[/bold]"))
    log_table = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan")
    log_table.add_column("Log Line", style="dim", no_wrap=False)

    for log in SAMPLE_LOGS:
        if "ERROR" in log:
            log_table.add_row(f"[red]{log}[/red]")
        elif "WARN" in log:
            log_table.add_row(f"[yellow]{log}[/yellow]")
        else:
            log_table.add_row(log)

    console.print(log_table)

    # -----------------------------------------------------------------------
    # Step 2: Stream deep analysis (SMART_MODEL)
    # -----------------------------------------------------------------------
    console.print(Rule("[bold]Streaming Deep Analysis (SMART_MODEL)[/bold]"))
    console.print("[dim]Watch the analysis appear in real time...[/dim]\n")

    try:
        analyze_logs_streaming(SAMPLE_LOGS)
    except Exception as e:
        console.print(f"[red]Error during streaming analysis: {e}[/red]")
        return

    # -----------------------------------------------------------------------
    # Step 3: Metric analysis (FAST_MODEL)
    # -----------------------------------------------------------------------
    console.print(Rule("[bold]Metric Analysis (FAST_MODEL)[/bold]"))
    console.print("[dim]Using fast model for metric classification...[/dim]\n")

    try:
        metric_result = analyze_metrics(SAMPLE_METRICS)

        metrics_table = Table(box=box.ROUNDED, show_header=False)
        metrics_table.add_column("Field", style="bold cyan", width=15)
        metrics_table.add_column("Value")

        risk_color = {
            "critical": "red",
            "high": "orange3",
            "medium": "yellow",
            "low": "green",
        }.get(metric_result.get("risk_level", "unknown"), "white")

        metrics_table.add_row("Summary", metric_result.get("summary", "N/A"))
        metrics_table.add_row("Trend", metric_result.get("trend", "N/A"))
        metrics_table.add_row(
            "Risk Level",
            f"[{risk_color}]{metric_result.get('risk_level', 'N/A').upper()}[/{risk_color}]",
        )
        metrics_table.add_row("Bottleneck", metric_result.get("bottleneck", "N/A"))

        console.print(Panel(metrics_table, title="Metric Analysis Result", border_style="blue"))
    except Exception as e:
        console.print(f"[red]Error during metric analysis: {e}[/red]")

    # -----------------------------------------------------------------------
    # Step 4: Anomaly detection
    # -----------------------------------------------------------------------
    console.print(Rule("[bold]Anomaly Detection[/bold]"))

    try:
        anomalies = detect_anomalies(SAMPLE_METRICS)

        if anomalies:
            console.print(f"[red]Found {len(anomalies)} anomalies:[/red]\n")
            for i, anomaly in enumerate(anomalies, 1):
                console.print(f"  [red]{i}.[/red] {anomaly}")
        else:
            console.print("[green]No anomalies detected.[/green]")
    except Exception as e:
        console.print(f"[red]Error during anomaly detection: {e}[/red]")

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    console.print()
    console.print(Panel(
        "[bold green]Module 01 Complete[/bold green]\n\n"
        "Optimizations used:\n"
        "  [cyan]STREAMING[/cyan]        - Real-time output, better UX for long analyses\n"
        "  [cyan]MODEL SELECTION[/cyan]  - FAST for metrics, SMART for log correlation\n",
        expand=False,
        border_style="green",
    ))


if __name__ == "__main__":
    main()
