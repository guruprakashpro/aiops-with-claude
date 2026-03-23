"""
Parallel Alert Triage with asyncio

Optimization: PARALLEL PROCESSING with asyncio

Sequential triage: alerts processed one by one, total time = N * latency_per_alert
Parallel triage: all alerts sent simultaneously, total time ≈ max(latency_per_alert)

For 8 alerts at ~1s each:
- Sequential: ~8 seconds
- Parallel: ~1-2 seconds (up to 4-8x speedup)

This uses asyncio.gather() to fan out all requests simultaneously
and collect results when all complete.
"""

import sys
import os
import asyncio
import time
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from groq import AsyncGroq
from rich.console import Console
from rich.table import Table
from rich import box

from src.llm_client import FAST_MODEL
from src.03_alert_triage.triage import AlertTriage, TRIAGE_SYSTEM_PROMPT

console = Console()


async def triage_alert_async(alert: str, client: AsyncGroq) -> AlertTriage:
    """
    Async version of triage_alert - can run concurrently with other calls.

    Uses the AsyncGroq client which returns awaitable coroutines,
    allowing the event loop to switch to other tasks while waiting for I/O.

    Args:
        alert: Raw alert text
        client: AsyncGroq client instance (shared across calls)

    Returns:
        AlertTriage result
    """
    messages = [
        {"role": "system", "content": TRIAGE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""Triage this alert. Respond with a JSON object containing exactly these fields:
- severity: "P1" | "P2" | "P3" | "P4"
- category: "performance" | "availability" | "security" | "capacity" | "data"
- summary: one-sentence description of what is happening
- suggested_action: the single most important action to take right now
- escalate_to_human: true/false
- estimated_resolution_minutes: integer
- affected_component: primary service or component name
- runbook_hint: brief hint about which runbook or procedure applies

Alert:
{alert}""",
        },
    ]

    try:
        response = await client.chat.completions.create(
            model=FAST_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        raw = response.choices[0].message.content
        data = json.loads(raw)
        return AlertTriage(**data)
    except Exception as e:
        return AlertTriage(
            severity="P2",
            category="availability",
            summary=f"Triage failed: {str(e)[:100]}",
            suggested_action="Manual review required",
            escalate_to_human=True,
            estimated_resolution_minutes=30,
        )


async def batch_triage_parallel(alerts: list[str]) -> tuple[list[AlertTriage], float]:
    """
    Triage all alerts in parallel using asyncio.gather().

    Key insight: asyncio.gather() launches all coroutines simultaneously.
    The event loop handles I/O waiting efficiently - while one request
    is waiting for the API, others can be processed.

    Args:
        alerts: List of alert strings

    Returns:
        Tuple of (results list, elapsed_seconds)
    """
    # AsyncGroq is the async version of the Groq client
    async_client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY"))

    console.print(f"[cyan]Launching {len(alerts)} requests in parallel...[/cyan]")
    start = time.time()

    # asyncio.gather() runs all coroutines concurrently
    # Results are returned in the same order as the input list
    results = await asyncio.gather(
        *[triage_alert_async(alert, async_client) for alert in alerts],
        return_exceptions=False,  # Exceptions propagate normally
    )

    elapsed = time.time() - start
    return list(results), elapsed


def run_parallel_triage(alerts: list[str]) -> tuple[list[AlertTriage], float]:
    """
    Synchronous wrapper to run the async parallel triage.
    Suitable for calling from non-async code.
    """
    return asyncio.run(batch_triage_parallel(alerts))


def print_triage_comparison(
    sequential_results: list[AlertTriage],
    sequential_time: float,
    parallel_results: list[AlertTriage],
    parallel_time: float,
) -> None:
    """Print a side-by-side timing and results comparison table."""
    speedup = sequential_time / parallel_time if parallel_time > 0 else 1.0

    # Timing summary
    timing_table = Table(box=box.ROUNDED, title="Sequential vs Parallel Comparison")
    timing_table.add_column("Method", style="bold")
    timing_table.add_column("Time", justify="right")
    timing_table.add_column("Speedup", justify="right")

    timing_table.add_row(
        "[yellow]Sequential[/yellow]",
        f"{sequential_time:.2f}s",
        "1.0x (baseline)",
    )
    timing_table.add_row(
        "[green]Parallel[/green]",
        f"[green]{parallel_time:.2f}s[/green]",
        f"[green]{speedup:.1f}x faster[/green]",
    )

    console.print(timing_table)
    console.print()

    # Results table
    results_table = Table(
        box=box.ROUNDED,
        title="Triage Results",
        show_header=True,
        header_style="bold cyan",
    )
    results_table.add_column("#", width=3)
    results_table.add_column("Severity", width=6)
    results_table.add_column("Category", width=14)
    results_table.add_column("Escalate?", width=9)
    results_table.add_column("ETA (min)", width=9, justify="right")
    results_table.add_column("Summary")

    severity_colors = {"P1": "red", "P2": "orange3", "P3": "yellow", "P4": "dim"}

    for i, result in enumerate(parallel_results, 1):
        color = severity_colors.get(result.severity, "white")
        results_table.add_row(
            str(i),
            f"[{color}]{result.severity}[/{color}]",
            result.category,
            "[red]YES[/red]" if result.escalate_to_human else "[green]No[/green]",
            str(result.estimated_resolution_minutes),
            result.summary[:70] + ("..." if len(result.summary) > 70 else ""),
        )

    console.print(results_table)
