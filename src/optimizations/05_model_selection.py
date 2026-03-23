"""
Optimization 05: Smart Model Selection

CONCEPT:
Not every task needs the most powerful (and slowest/costliest) model.
Route tasks intelligently:
  - Simple classification → FAST model (llama-3.1-8b-instant)
  - Complex reasoning    → SMART model (llama-3.3-70b-versatile)

BENEFITS:
- 3-5x faster responses for simple tasks
- Lower cost in paid tiers
- Better throughput (fast model handles more concurrent requests)
- Save smart model capacity for tasks that actually need it

DECISION RULES:
  FAST model:  classification, yes/no, severity label, short summaries
  SMART model: root cause analysis, multi-step reasoning, runbook generation

Run: python src/optimizations/05_model_selection.py
"""

import sys
import os
import time
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich import box

from src.llm_client import LLMClient, FAST_MODEL, SMART_MODEL

console = Console()
client = LLMClient()

# -----------------------------------------------------------------------
# Task definitions: simple vs complex
# -----------------------------------------------------------------------
SIMPLE_TASKS = [
    {
        "name": "Severity Classification",
        "prompt": "Classify severity (P1/P2/P3/P4) for: 'CPU at 95% on prod web server'. Reply with just the severity label.",
        "why_fast": "Single label output, no reasoning chain needed",
    },
    {
        "name": "Binary Alert Filter",
        "prompt": "Is this alert actionable? 'Scheduled maintenance window started'. Reply YES or NO only.",
        "why_fast": "Binary decision, pattern matching",
    },
    {
        "name": "Service Name Extraction",
        "prompt": "Extract the service name from: 'Error in payment-service: timeout connecting to stripe'. Reply with just the service name.",
        "why_fast": "Simple extraction, no reasoning",
    },
    {
        "name": "Log Level Summary",
        "prompt": "Count errors in: [INFO ok, ERROR fail, WARN slow, ERROR crash, INFO ok]. Reply: 'X errors, Y warnings'.",
        "why_fast": "Counting / simple aggregation",
    },
]

COMPLEX_TASKS = [
    {
        "name": "Root Cause Analysis",
        "prompt": (
            "Analyze this incident and provide a detailed root cause analysis:\n"
            "Service: order-processor\n"
            "Symptoms: 23% error rate, latency P99=4500ms, started after deploy v3.1.2\n"
            "Errors: 'Connection pool exhausted' and 'Redis timeout after 5000ms'\n"
            "Recent changes: added async task queue, upgraded Redis client library\n"
            "Provide: root cause, contributing factors, remediation steps."
        ),
        "why_smart": "Multi-factor reasoning, causal chains, technical depth needed",
    },
    {
        "name": "Incident Runbook Generation",
        "prompt": (
            "Generate a complete incident runbook for: 'Kubernetes pod OOMKilled in production'\n"
            "Include: detection steps, immediate actions, investigation commands, "
            "short-term fix, long-term prevention, escalation criteria."
        ),
        "why_smart": "Multi-section document, domain expertise, structured output",
    },
    {
        "name": "Architecture Risk Assessment",
        "prompt": (
            "Assess operational risks in this architecture:\n"
            "- Single Redis instance (no replica) used for session store and job queue\n"
            "- All microservices share one PostgreSQL instance\n"
            "- No circuit breakers between payment-service and external Stripe API\n"
            "- Kubernetes cluster in single AZ\n"
            "Provide risk ratings (High/Medium/Low), failure scenarios, and mitigations."
        ),
        "why_smart": "Complex trade-off analysis, multi-domain expertise",
    },
]


def benchmark_task(task: dict, model: str) -> tuple[str, float, int]:
    """Run a task on a model and return (response, latency, approx_tokens)."""
    start = time.time()
    response = client.complete(
        messages=[
            {"role": "system", "content": "You are an expert SRE."},
            {"role": "user", "content": task["prompt"]},
        ],
        model=model,
        temperature=0.1,
    )
    latency = time.time() - start
    tokens = client.last_usage.get("total_tokens", len(response.split()) * 1.3)
    return response, latency, int(tokens)


def main():
    console.print()
    console.print(Panel(
        "[bold green]Optimization 05: Smart Model Selection[/bold green]\n"
        "[dim]Route tasks to the right model — fast for simple, smart for complex[/dim]",
        expand=False,
        border_style="green",
    ))

    # Model overview
    model_table = Table(title="Available Models", box=box.ROUNDED)
    model_table.add_column("Model", style="bold")
    model_table.add_column("Speed", justify="center")
    model_table.add_column("Reasoning", justify="center")
    model_table.add_column("Best For")

    model_table.add_row(
        f"[green]{FAST_MODEL}[/green]",
        "[green]⚡ Very Fast[/green]",
        "[yellow]Basic[/yellow]",
        "Classification, extraction, yes/no, short labels",
    )
    model_table.add_row(
        f"[blue]{SMART_MODEL}[/blue]",
        "[yellow]Moderate[/yellow]",
        "[green]🧠 Deep[/green]",
        "RCA, runbooks, risk analysis, multi-step reasoning",
    )
    console.print(model_table)

    all_results = []

    # -----------------------------------------------------------------------
    # Simple tasks: compare fast vs smart
    # -----------------------------------------------------------------------
    console.print(Rule("[bold yellow]Simple Tasks → FAST model[/bold yellow]"))

    for task in SIMPLE_TASKS:
        console.print(f"\n[bold]{task['name']}[/bold] [dim]({task['why_fast']})[/dim]")

        fast_resp, fast_lat, fast_tok = benchmark_task(task, FAST_MODEL)
        smart_resp, smart_lat, smart_tok = benchmark_task(task, SMART_MODEL)

        console.print(f"  [green]Fast ({FAST_MODEL}):[/green]  {fast_resp.strip()[:80]}  [{fast_lat:.2f}s]")
        console.print(f"  [blue]Smart ({SMART_MODEL[:20]}):[/blue] {smart_resp.strip()[:80]}  [{smart_lat:.2f}s]")

        all_results.append({
            "task": task["name"],
            "type": "Simple",
            "recommended": "FAST",
            "fast_latency": fast_lat,
            "smart_latency": smart_lat,
            "speedup": smart_lat / fast_lat if fast_lat > 0 else 1,
        })

    # -----------------------------------------------------------------------
    # Complex tasks: compare fast vs smart
    # -----------------------------------------------------------------------
    console.print(Rule("[bold blue]Complex Tasks → SMART model[/bold blue]"))

    for task in COMPLEX_TASKS:
        console.print(f"\n[bold]{task['name']}[/bold] [dim]({task['why_smart']})[/dim]")

        smart_resp, smart_lat, smart_tok = benchmark_task(task, SMART_MODEL)
        fast_resp, fast_lat, fast_tok = benchmark_task(task, FAST_MODEL)

        console.print(f"  [blue]Smart response preview:[/blue] {smart_resp.strip()[:120]}...")
        console.print(f"  [dim]Fast response preview:  {fast_resp.strip()[:120]}...[/dim]")
        console.print(f"  [green]Smart model time: {smart_lat:.2f}s[/green]  |  Fast model time: {fast_lat:.2f}s")

        all_results.append({
            "task": task["name"],
            "type": "Complex",
            "recommended": "SMART",
            "fast_latency": fast_lat,
            "smart_latency": smart_lat,
            "speedup": fast_lat / smart_lat if smart_lat > 0 else 1,
        })

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    console.print(Rule("[bold]Results Summary[/bold]"))
    summary = Table(title="Model Selection Benchmark", box=box.ROUNDED)
    summary.add_column("Task", style="cyan")
    summary.add_column("Type", justify="center")
    summary.add_column("Recommended", justify="center")
    summary.add_column("Fast Model", justify="right", style="green")
    summary.add_column("Smart Model", justify="right", style="blue")
    summary.add_column("Savings")

    for r in all_results:
        if r["recommended"] == "FAST":
            savings = f"[green]{r['speedup']:.1f}x faster[/green]"
        else:
            savings = f"Better quality"
        summary.add_row(
            r["task"],
            r["type"],
            f"[{'green' if r['recommended'] == 'FAST' else 'blue'}]{r['recommended']}[/{'green' if r['recommended'] == 'FAST' else 'blue'}]",
            f"{r['fast_latency']:.2f}s",
            f"{r['smart_latency']:.2f}s",
            savings,
        )
    console.print(summary)

    console.print(Panel(
        "[bold]Model Selection Decision Tree:[/bold]\n\n"
        "Is the output a [cyan]label, number, or yes/no[/cyan]?\n"
        "  → [green]FAST model[/green]\n\n"
        "Does it require [cyan]multi-step reasoning or domain expertise[/cyan]?\n"
        "  → [blue]SMART model[/blue]\n\n"
        "Is it a [cyan]user-facing real-time response[/cyan]?\n"
        "  → [green]FAST model[/green] (latency matters)\n\n"
        "Is it a [cyan]background batch job[/cyan] needing accuracy?\n"
        "  → [blue]SMART model[/blue] (latency less critical)\n\n"
        "[bold]Rule of thumb:[/bold] Start with FAST. Only upgrade to SMART if quality is insufficient.",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
