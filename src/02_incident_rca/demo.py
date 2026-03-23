"""
Demo: Incident RCA with Tool Use Agentic Loop

Run: python src/02_incident_rca/demo.py

Demonstrates:
- Tool use / function calling with Groq
- Agentic loop: LLM calls tools iteratively until satisfied
- Structured output parsing with Pydantic
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich import box

from src.02_incident_rca.rca_agent import RCAAgent, RCAResult

console = Console()

# ---------------------------------------------------------------------------
# Sample incidents for the demo
# ---------------------------------------------------------------------------
SAMPLE_INCIDENTS = [
    {
        "title": "API Gateway Error Spike",
        "description": (
            "Starting approximately 15 minutes ago, the api-gateway began returning 503 errors "
            "at a rate exceeding 60%. Customer support reports users cannot log in or place orders. "
            "The on-call alert fired at 14:23 UTC. No planned maintenance was scheduled."
        ),
    },
    {
        "title": "Database Connection Exhaustion",
        "description": (
            "The database connection pool (db-pool) has been fully exhausted for the past 20 minutes. "
            "50/50 connections are in use with 28 requests queued. A long-running query has been "
            "identified in the order-processor service. New connections cannot be acquired within the "
            "5-second timeout, causing cascading failures in auth-service and api-gateway."
        ),
    },
    {
        "title": "Cascading Authentication Failure",
        "description": (
            "Auth-service is experiencing a 22% error rate causing login failures. "
            "Users report being logged out and unable to re-authenticate. The issue started "
            "roughly 10 minutes after the last deployment window. Mobile and web clients both affected."
        ),
    },
]


def print_rca_result(result: RCAResult, incident_title: str) -> None:
    """Pretty-print an RCAResult using Rich."""
    confidence_pct = int(result.confidence_score * 100)
    confidence_color = (
        "green" if confidence_pct >= 80
        else "yellow" if confidence_pct >= 60
        else "red"
    )

    # Root cause panel
    console.print(Panel(
        f"[bold white]{result.root_cause}[/bold white]",
        title=f"[bold red]Root Cause - {incident_title}[/bold red]",
        border_style="red",
    ))

    # Details table
    table = Table(box=box.ROUNDED, show_header=False, padding=(0, 1))
    table.add_column("Field", style="bold cyan", width=22)
    table.add_column("Value")

    table.add_row(
        "Confidence",
        f"[{confidence_color}]{confidence_pct}%[/{confidence_color}]",
    )
    table.add_row(
        "Deployment Related",
        "[red]YES[/red]" if result.deployment_related else "[green]No[/green]",
    )
    table.add_row(
        "Affected Services",
        ", ".join(f"[yellow]{s}[/yellow]" for s in result.affected_services),
    )

    if result.contributing_factors:
        table.add_row(
            "Contributing Factors",
            "\n".join(f"• {f}" for f in result.contributing_factors),
        )

    console.print(table)

    # Recommended actions
    console.print("\n[bold green]Recommended Actions:[/bold green]")
    for i, action in enumerate(result.recommended_actions, 1):
        console.print(f"  [green]{i}.[/green] {action}")
    console.print()


def main():
    console.print()
    console.print(Panel(
        "[bold green]Module 02: Incident RCA[/bold green]\n"
        "[dim]Optimization: Tool Use Agentic Loop[/dim]",
        expand=False,
        border_style="green",
    ))

    console.print(Panel(
        "[bold]How the Agentic Loop Works:[/bold]\n\n"
        "1. [cyan]Send[/cyan] incident + tools to LLM\n"
        "2. [cyan]LLM[/cyan] requests tool calls to gather data\n"
        "3. [cyan]Execute[/cyan] tools, feed results back\n"
        "4. [cyan]Repeat[/cyan] until LLM has enough info\n"
        "5. [cyan]Parse[/cyan] final response into structured RCAResult",
        title="Optimization: Tool Use",
        border_style="blue",
        expand=False,
    ))

    agent = RCAAgent(verbose=True)

    for i, incident in enumerate(SAMPLE_INCIDENTS, 1):
        console.print(Rule(f"[bold]Incident {i}: {incident['title']}[/bold]"))
        console.print(f"[dim]{incident['description']}[/dim]\n")

        try:
            result = agent.investigate(incident["description"])
            print_rca_result(result, incident["title"])
        except Exception as e:
            console.print(f"[red]Error investigating incident: {e}[/red]\n")

    # Summary
    console.print(Panel(
        "[bold green]Module 02 Complete[/bold green]\n\n"
        "Optimizations used:\n"
        "  [cyan]TOOL USE[/cyan]         - LLM calls real functions to gather data\n"
        "  [cyan]AGENTIC LOOP[/cyan]     - Iterative investigation until confident\n"
        "  [cyan]STRUCTURED OUTPUT[/cyan]- Pydantic validates the final RCA result",
        expand=False,
        border_style="green",
    ))


if __name__ == "__main__":
    main()
