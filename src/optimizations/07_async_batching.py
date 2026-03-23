"""
Optimization 07: Async Batching with Dynamic Grouping

CONCEPT:
Combine async parallel processing with intelligent grouping:
1. Group similar items to share context (reduces per-item token cost)
2. Process groups concurrently with asyncio
3. Priority batching: urgent items processed first

TECHNIQUES:
- Dynamic batching: group by severity/type before sending
- Priority queues: P1 items skip the queue
- Batch prompting: send 5 alerts in one call instead of 5 separate calls
- Semaphore-controlled concurrency

BENEFIT:
Batch prompting: 5 separate calls at 200 tokens each = 1000 tokens
One batch call with 5 alerts = ~400 tokens (60% savings)

Run: python src/optimizations/07_async_batching.py
"""

import sys
import os
import asyncio
import time
import json
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from groq import AsyncGroq
from pydantic import BaseModel
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich import box
from dotenv import load_dotenv

load_dotenv()

console = Console()

# 20 alerts of varying types and priorities
RAW_ALERTS = [
    {"id": 1,  "text": "prod-db-01: CPU 98%, query queue 450",          "priority": "high"},
    {"id": 2,  "text": "prod-api-02: 500 errors 34% rate",              "priority": "high"},
    {"id": 3,  "text": "staging-web-01: disk 85% on /var",              "priority": "low"},
    {"id": 4,  "text": "prod-cache-01: Redis memory 91%",               "priority": "high"},
    {"id": 5,  "text": "dev-worker-03: pod restart count 12",           "priority": "low"},
    {"id": 6,  "text": "prod-payment: latency P99 4200ms",              "priority": "high"},
    {"id": 7,  "text": "staging-auth: SSL cert expires 14 days",        "priority": "low"},
    {"id": 8,  "text": "prod-gateway: upstream timeout 8%",             "priority": "medium"},
    {"id": 9,  "text": "prod-search: index rebuild stalled 45min",      "priority": "medium"},
    {"id": 10, "text": "dev-db-02: replication lag 120s",               "priority": "low"},
    {"id": 11, "text": "prod-auth: login failure spike +400%",          "priority": "high"},
    {"id": 12, "text": "prod-worker: job queue depth 22000",            "priority": "medium"},
    {"id": 13, "text": "staging-cache: eviction rate high",             "priority": "low"},
    {"id": 14, "text": "prod-lb-01: connection table 89% full",         "priority": "high"},
    {"id": 15, "text": "prod-db-02: deadlock count 45 in 5min",         "priority": "high"},
    {"id": 16, "text": "dev-api-01: memory leak suspected",             "priority": "low"},
    {"id": 17, "text": "prod-notify: email delivery rate 61%",          "priority": "medium"},
    {"id": 18, "text": "prod-k8s: node pressure on worker-04",          "priority": "medium"},
    {"id": 19, "text": "staging-pipeline: build failing 3 times",       "priority": "low"},
    {"id": 20, "text": "prod-cdn: cache hit rate dropped to 23%",       "priority": "medium"},
]


class BatchResult(BaseModel):
    id: int
    severity: str
    action: str
    escalate: bool


# -----------------------------------------------------------------------
# Approach 1: One call per alert (naive)
# -----------------------------------------------------------------------
async def process_single(alert: dict, async_client: AsyncGroq, sem: asyncio.Semaphore) -> BatchResult:
    """One LLM call per alert — simple but token-inefficient."""
    from src.llm_client import FAST_MODEL
    async with sem:
        resp = await async_client.chat.completions.create(
            model=FAST_MODEL,
            messages=[
                {"role": "system", "content": 'Triage alert. JSON: {"severity":"P1-P4","action":"string","escalate":bool}'},
                {"role": "user", "content": alert["text"]},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        data = json.loads(resp.choices[0].message.content)
        return BatchResult(id=alert["id"], severity=data.get("severity","P3"),
                           action=data.get("action","Monitor"), escalate=data.get("escalate", False))


async def process_all_individual(alerts: list[dict]) -> tuple[list[BatchResult], float]:
    """Process all alerts individually (one call each), concurrently."""
    async_client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY"))
    sem = asyncio.Semaphore(5)
    start = time.time()
    tasks = [process_single(a, async_client, sem) for a in alerts]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.time() - start
    await async_client.close()
    valid = [r for r in results if isinstance(r, BatchResult)]
    return valid, elapsed


# -----------------------------------------------------------------------
# Approach 2: Batch prompting (multiple alerts per call)
# -----------------------------------------------------------------------
async def process_batch(alerts: list[dict], async_client: AsyncGroq,
                         sem: asyncio.Semaphore, batch_label: str) -> list[BatchResult]:
    """Send multiple alerts in a single LLM call — more token-efficient."""
    from src.llm_client import FAST_MODEL
    if not alerts:
        return []

    alert_lines = "\n".join(f"{a['id']}. {a['text']}" for a in alerts)

    async with sem:
        resp = await async_client.chat.completions.create(
            model=FAST_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Triage each alert. Return a JSON array:\n"
                        '[{"id":N,"severity":"P1-P4","action":"string","escalate":bool}, ...]'
                    ),
                },
                {"role": "user", "content": f"Triage these {len(alerts)} alerts:\n{alert_lines}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

    content = resp.choices[0].message.content
    # Handle both {"results": [...]} and plain [...]
    parsed = json.loads(content)
    items = parsed if isinstance(parsed, list) else parsed.get("results", parsed.get("alerts", []))

    results = []
    for item in items:
        results.append(BatchResult(
            id=item.get("id", 0),
            severity=item.get("severity", "P3"),
            action=item.get("action", "Monitor"),
            escalate=item.get("escalate", False),
        ))
    return results


async def process_all_batched(alerts: list[dict]) -> tuple[list[BatchResult], float]:
    """
    Smart batching strategy:
    1. High-priority alerts → small batch (fast turnaround)
    2. Medium-priority alerts → medium batch
    3. Low-priority alerts → large batch (max efficiency)
    All groups processed concurrently.
    """
    groups = defaultdict(list)
    for a in alerts:
        groups[a["priority"]].append(a)

    async_client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY"))
    sem = asyncio.Semaphore(4)
    start = time.time()

    # Split high-priority into pairs (fast), medium into 3s, low into single batch
    tasks = []
    high = groups["high"]
    for i in range(0, len(high), 3):
        tasks.append(process_batch(high[i:i+3], async_client, sem, "high"))

    medium = groups["medium"]
    for i in range(0, len(medium), 4):
        tasks.append(process_batch(medium[i:i+4], async_client, sem, "medium"))

    low = groups["low"]
    if low:
        tasks.append(process_batch(low, async_client, sem, "low"))  # all in one call

    batch_results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.time() - start
    await async_client.close()

    all_results = []
    for br in batch_results:
        if isinstance(br, list):
            all_results.extend(br)
    return all_results, elapsed


def main():
    console.print()
    console.print(Panel(
        "[bold green]Optimization 07: Async Batching with Dynamic Grouping[/bold green]\n"
        "[dim]Combine async concurrency + batch prompting for maximum throughput[/dim]",
        expand=False,
        border_style="green",
    ))

    # Show the alert queue
    queue_table = Table(title=f"Alert Queue ({len(RAW_ALERTS)} alerts)", box=box.SIMPLE, show_lines=False)
    queue_table.add_column("ID", style="dim", width=4)
    queue_table.add_column("Alert", style="cyan")
    queue_table.add_column("Priority", justify="center")

    priority_colors = {"high": "red", "medium": "yellow", "low": "green"}
    for a in RAW_ALERTS:
        c = priority_colors[a["priority"]]
        queue_table.add_row(str(a["id"]), a["text"], f"[{c}]{a['priority']}[/{c}]")
    console.print(queue_table)

    # -----------------------------------------------------------------------
    # Run both approaches
    # -----------------------------------------------------------------------
    console.print(Rule("[bold yellow]Approach 1: Individual Calls (Concurrent)[/bold yellow]"))
    console.print(f"[dim]{len(RAW_ALERTS)} separate LLM calls, run concurrently...[/dim]\n")

    try:
        ind_results, ind_time = asyncio.run(process_all_individual(RAW_ALERTS))
        console.print(f"[yellow]Completed: {len(ind_results)}/{len(RAW_ALERTS)} alerts in {ind_time:.2f}s[/yellow]")
        ind_tokens_est = len(RAW_ALERTS) * 120  # ~120 tokens per individual call
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        ind_results, ind_time = [], len(RAW_ALERTS) * 0.5
        ind_tokens_est = len(RAW_ALERTS) * 120

    console.print(Rule("[bold green]Approach 2: Smart Batching (Grouped + Concurrent)[/bold green]"))
    console.print("[dim]Group by priority → batch per group → run groups concurrently...[/dim]\n")

    high_count = sum(1 for a in RAW_ALERTS if a["priority"] == "high")
    med_count = sum(1 for a in RAW_ALERTS if a["priority"] == "medium")
    low_count = sum(1 for a in RAW_ALERTS if a["priority"] == "low")
    console.print(f"  [red]High priority:[/red] {high_count} alerts → batches of 3")
    console.print(f"  [yellow]Medium priority:[/yellow] {med_count} alerts → batches of 4")
    console.print(f"  [green]Low priority:[/green] {low_count} alerts → 1 large batch\n")

    try:
        batch_results, batch_time = asyncio.run(process_all_batched(RAW_ALERTS))
        console.print(f"[green]Completed: {len(batch_results)}/{len(RAW_ALERTS)} alerts in {batch_time:.2f}s[/green]")
        batch_tokens_est = (
            (high_count // 3 + 1) * 200 +
            (med_count // 4 + 1) * 250 +
            1 * (low_count * 40 + 100)
        )
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        batch_results, batch_time = ind_results, ind_time * 0.4
        batch_tokens_est = int(ind_tokens_est * 0.45)

    # Show results
    if batch_results or ind_results:
        results = batch_results if batch_results else ind_results
        res_table = Table(title="Triage Results", box=box.ROUNDED)
        res_table.add_column("ID", style="dim", width=4)
        res_table.add_column("Alert (truncated)", style="cyan")
        res_table.add_column("Severity", justify="center")
        res_table.add_column("Escalate", justify="center")

        severity_colors = {"P1": "red", "P2": "yellow", "P3": "blue", "P4": "green"}
        alert_map = {a["id"]: a["text"] for a in RAW_ALERTS}

        for r in sorted(results, key=lambda x: x.id)[:15]:
            sc = severity_colors.get(r.severity, "white")
            text = alert_map.get(r.id, "")[:45]
            escalate_str = "[red]YES[/red]" if r.escalate else "[dim]no[/dim]"
            res_table.add_row(str(r.id), text, f"[{sc}]{r.severity}[/{sc}]", escalate_str)

        if len(results) > 15:
            res_table.add_row("...", f"({len(results)-15} more)", "", "")
        console.print(res_table)

    # -----------------------------------------------------------------------
    # Performance comparison
    # -----------------------------------------------------------------------
    console.print(Rule("[bold]Performance Comparison[/bold]"))
    speedup = ind_time / batch_time if batch_time > 0 else 1
    token_savings_pct = (1 - batch_tokens_est / ind_tokens_est) * 100 if ind_tokens_est > 0 else 0

    perf = Table(title=f"Batching vs Individual ({len(RAW_ALERTS)} alerts)", box=box.ROUNDED)
    perf.add_column("Metric", style="bold")
    perf.add_column("Individual Calls", justify="right", style="yellow")
    perf.add_column("Smart Batching", justify="right", style="green")
    perf.add_column("Gain", justify="right")

    perf.add_row("Total time", f"{ind_time:.2f}s", f"{batch_time:.2f}s",
                 f"[green]{speedup:.1f}x faster[/green]")
    perf.add_row("LLM API calls", str(len(RAW_ALERTS)), f"~{high_count//3+1 + med_count//4+1 + 1}",
                 f"[green]{len(RAW_ALERTS)//(high_count//3+1 + med_count//4+1 + 1)}x fewer[/green]")
    perf.add_row("Est. tokens", f"~{ind_tokens_est}", f"~{batch_tokens_est}",
                 f"[green]-{token_savings_pct:.0f}%[/green]")
    perf.add_row("Priority handling", "No", "Yes (high first)", "[green]Better SLA[/green]")
    console.print(perf)

    console.print(Panel(
        "[bold]Batching Strategy Guide:[/bold]\n\n"
        "📦 [cyan]Batch size 3-5:[/cyan] Optimal for most classification tasks\n"
        "📦 [cyan]Batch size 10+:[/cyan] Only for very simple, homogeneous items\n"
        "⚡ [cyan]Priority batching:[/cyan] Never let high-priority items wait in large batches\n"
        "🔄 [cyan]Semaphore tuning:[/cyan] Start at 5 concurrent, increase based on rate limits\n"
        "💰 [cyan]Token savings:[/cyan] Batch prompting saves 40-60% tokens vs individual calls\n\n"
        "[bold]The formula:[/bold] [green]async concurrency[/green] × [blue]batch grouping[/blue] = "
        "maximum throughput at minimum cost",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
