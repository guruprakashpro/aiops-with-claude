"""
Demo: Anomaly Detection with Multi-Turn Conversation

Run: python src/05_anomaly_detection/demo.py

Demonstrates:
- Maintaining conversation history across multiple metric snapshots
- Context management (trimming old history)
- Follow-up questions that reference previous analysis
"""

import sys
import os
from datetime import datetime, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich import box

from src.05_anomaly_detection.detector import AnomalyDetector, AnomalyReport

console = Console()

# ---------------------------------------------------------------------------
# Simulate 3 time-window metric snapshots showing a degradation pattern
# ---------------------------------------------------------------------------

now = datetime.now()

METRIC_SNAPSHOTS = [
    # Snapshot 1: Early warning signs
    {
        "timestamp": (now - timedelta(minutes=15)).strftime("%H:%M:%S"),
        "cpu_usage_pct": 58.9,
        "memory_usage_pct": 68.9,
        "request_rate_per_min": 1289,
        "error_rate_pct": 2.40,
        "latency_p99_ms": 892,
        "db_connections_active": 38,
        "db_connections_max": 50,
        "cache_hit_ratio_pct": 88.4,
        "queue_depth": 5,
    },
    # Snapshot 2: Escalating issue
    {
        "timestamp": (now - timedelta(minutes=10)).strftime("%H:%M:%S"),
        "cpu_usage_pct": 79.1,
        "memory_usage_pct": 78.8,
        "request_rate_per_min": 834,
        "error_rate_pct": 21.34,
        "latency_p99_ms": 5892,
        "db_connections_active": 50,
        "db_connections_max": 50,
        "cache_hit_ratio_pct": 65.3,
        "queue_depth": 18,
    },
    # Snapshot 3: Critical state
    {
        "timestamp": (now - timedelta(minutes=5)).strftime("%H:%M:%S"),
        "cpu_usage_pct": 94.1,
        "memory_usage_pct": 89.4,
        "request_rate_per_min": 445,
        "error_rate_pct": 61.43,
        "latency_p99_ms": 12400,
        "db_connections_active": 50,
        "db_connections_max": 50,
        "cache_hit_ratio_pct": 55.1,
        "queue_depth": 28,
    },
]

# Follow-up questions to ask after the analysis
FOLLOW_UP_QUESTIONS = [
    "Based on the trends you've seen across all three snapshots, what is the rate of deterioration for error_rate_pct and what does that imply for the next 5 minutes?",
    "Which metric reached its limit first and what does that tell us about the root cause?",
]


def print_anomaly_report(report: AnomalyReport, snapshot_num: int) -> None:
    """Pretty-print an AnomalyReport."""
    severity_colors = {
        "critical": "red",
        "high": "orange3",
        "medium": "yellow",
        "low": "blue",
        "normal": "green",
        "unknown": "dim",
    }
    trend_icons = {
        "worsening": "[red]↓ Worsening[/red]",
        "stable": "[yellow]→ Stable[/yellow]",
        "improving": "[green]↑ Improving[/green]",
        "unknown": "[dim]? Unknown[/dim]",
    }

    sev_color = severity_colors.get(report.severity, "white")
    trend_str = trend_icons.get(report.trend, report.trend)

    content = (
        f"[bold]Severity:[/bold] [{sev_color}]{report.severity.upper()}[/{sev_color}]  "
        f"[bold]Trend:[/bold] {trend_str}  "
        f"[bold]Action Required:[/bold] {'[red]YES[/red]' if report.action_required else '[green]No[/green]'}\n\n"
    )

    if report.anomalies:
        content += "[bold red]Anomalies Detected:[/bold red]\n"
        for anomaly in report.anomalies:
            content += f"  • {anomaly}\n"
        content += "\n"

    if report.key_metric:
        content += f"[bold]Key Metric:[/bold] {report.key_metric}\n"

    content += f"[bold]Prediction:[/bold] {report.prediction}\n"

    if report.estimated_time_to_breach:
        content += f"[bold red]Time to Breach:[/bold red] {report.estimated_time_to_breach}\n"

    console.print(Panel(
        content.strip(),
        title=f"[bold]Snapshot #{snapshot_num} Analysis[/bold]",
        border_style=sev_color,
    ))


def main():
    console.print()
    console.print(Panel(
        "[bold green]Module 05: Anomaly Detection[/bold green]\n"
        "[dim]Optimization: Multi-Turn Conversation + Context Management[/dim]",
        expand=False,
        border_style="green",
    ))

    console.print(Panel(
        "[bold]How Multi-Turn Context Works:[/bold]\n\n"
        "• Each metrics snapshot is added to conversation history\n"
        "• LLM can reference previous snapshots: 'CPU was 58% now 94%'\n"
        "• This enables trend detection impossible with stateless calls\n"
        "• _trim_history() prevents context overflow by keeping last N turns\n\n"
        "[bold]Without context:[/bold] 'error_rate is 61%'\n"
        "[bold]With context:[/bold] 'error_rate jumped from 2.4% → 21.3% → 61.4% - rapid deterioration'",
        title="Context Management",
        border_style="blue",
        expand=False,
    ))

    detector = AnomalyDetector()

    # -----------------------------------------------------------------------
    # Analyze each snapshot
    # -----------------------------------------------------------------------
    console.print(Rule("[bold]Analyzing 3 Time-Window Snapshots[/bold]"))

    for i, snapshot in enumerate(METRIC_SNAPSHOTS, 1):
        console.print(f"\n[bold cyan]Snapshot {i}/3 - {snapshot['timestamp']}[/bold cyan]")
        console.print(f"[dim]History length before: {detector.history_length()} messages[/dim]")

        # Show key metrics in a compact table
        snap_table = Table(box=box.SIMPLE, show_header=True, header_style="dim")
        snap_table.add_column("Metric", style="dim")
        snap_table.add_column("Value", justify="right")

        highlight_metrics = ["error_rate_pct", "latency_p99_ms", "db_connections_active", "cpu_usage_pct"]
        for metric in highlight_metrics:
            val = snapshot.get(metric, "N/A")
            val_str = str(val)
            if metric == "error_rate_pct" and isinstance(val, float) and val > 5:
                val_str = f"[red]{val}[/red]"
            elif metric == "latency_p99_ms" and isinstance(val, int) and val > 2000:
                val_str = f"[red]{val}ms[/red]"
            elif metric == "db_connections_active" and val == 50:
                val_str = f"[red]{val}/50 (FULL)[/red]"
            snap_table.add_row(metric, val_str)

        console.print(snap_table)

        try:
            report = detector.analyze(snapshot)
            print_anomaly_report(report, i)
            console.print(f"[dim]History length after: {detector.history_length()} messages[/dim]")
        except Exception as e:
            console.print(f"[red]Error analyzing snapshot: {e}[/red]")

    # -----------------------------------------------------------------------
    # Follow-up questions (uses conversation context)
    # -----------------------------------------------------------------------
    console.print(Rule("[bold]Follow-Up Questions (Multi-Turn Context)[/bold]"))
    console.print("[dim]These questions reference previous analysis...[/dim]\n")

    for q in FOLLOW_UP_QUESTIONS:
        console.print(Panel(f"[bold cyan]Q:[/bold cyan] {q}", border_style="cyan", expand=False))
        try:
            answer = detector.follow_up(q)
            console.print(Panel(answer, title="[bold]Answer[/bold]", border_style="green"))
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
        console.print()

    console.print(Panel(
        "[bold green]Module 05 Complete[/bold green]\n\n"
        "Optimizations used:\n"
        "  [cyan]MULTI-TURN[/cyan]          - Conversation history enables trend analysis\n"
        "  [cyan]CONTEXT MANAGEMENT[/cyan]  - _trim_history() prevents token overflow\n"
        "  [cyan]FOLLOW-UPS[/cyan]          - Iterative analysis without context loss",
        expand=False,
        border_style="green",
    ))


if __name__ == "__main__":
    main()
