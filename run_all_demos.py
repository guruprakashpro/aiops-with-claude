"""
AIops with Claude — Master Demo Runner

Run all optimization examples in sequence with a performance summary.
Usage: python run_all_demos.py [--quick] [--only 01,03,05]
"""

import sys
import os
import subprocess
import time
import argparse

sys.path.insert(0, os.path.dirname(__file__))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich import box

console = Console()

DEMOS = [
    {
        "id": "01",
        "name": "Streaming",
        "file": "src/optimizations/01_streaming.py",
        "description": "Streaming vs batch — real-time output, faster time-to-first-token",
        "technique": "Streaming API",
        "benefit": "10x faster perceived latency",
    },
    {
        "id": "02",
        "name": "Structured Output",
        "file": "src/optimizations/02_structured_output.py",
        "description": "JSON mode vs regex parsing — reliable structured data extraction",
        "technique": "JSON Mode + Pydantic",
        "benefit": "Zero parsing failures",
    },
    {
        "id": "03",
        "name": "Tool Use",
        "file": "src/optimizations/03_tool_use.py",
        "description": "Agentic loop with function calling — grounded answers from real data",
        "technique": "Tool Use / Function Calling",
        "benefit": "No hallucinations on system state",
    },
    {
        "id": "04",
        "name": "Parallel Processing",
        "file": "src/optimizations/04_parallel_processing.py",
        "description": "asyncio.gather() vs sequential — process N alerts in ~1x latency",
        "technique": "asyncio + Semaphore",
        "benefit": "10x speedup on batch jobs",
    },
    {
        "id": "05",
        "name": "Model Selection",
        "file": "src/optimizations/05_model_selection.py",
        "description": "Route tasks to the right model — fast for simple, smart for complex",
        "technique": "Model Routing",
        "benefit": "3-5x faster + lower cost",
    },
    {
        "id": "06",
        "name": "Prompt Optimization",
        "file": "src/optimizations/06_prompt_optimization.py",
        "description": "Concise prompts, format specs, few-shot examples, negative constraints",
        "technique": "Prompt Engineering",
        "benefit": "40-60% token reduction",
    },
    {
        "id": "07",
        "name": "Async Batching",
        "file": "src/optimizations/07_async_batching.py",
        "description": "Group alerts by priority + batch prompting for maximum throughput",
        "technique": "Batch Prompting + Async",
        "benefit": "60% token savings + speed",
    },
]


def run_demo(demo: dict) -> tuple[bool, float]:
    """Run a single demo, return (success, elapsed_seconds)."""
    start = time.time()
    try:
        result = subprocess.run(
            [sys.executable, demo["file"]],
            cwd=os.path.dirname(__file__),
            timeout=120,
        )
        elapsed = time.time() - start
        return result.returncode == 0, elapsed
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        console.print(f"  [red]Timed out after {elapsed:.0f}s[/red]")
        return False, elapsed
    except Exception as e:
        elapsed = time.time() - start
        console.print(f"  [red]Error: {e}[/red]")
        return False, elapsed


def main():
    parser = argparse.ArgumentParser(description="Run AIops optimization demos")
    parser.add_argument("--quick", action="store_true", help="Skip slow demos")
    parser.add_argument("--only", type=str, help="Comma-separated demo IDs, e.g. 01,03,05")
    args = parser.parse_args()

    demos_to_run = DEMOS
    if args.only:
        ids = set(args.only.split(","))
        demos_to_run = [d for d in DEMOS if d["id"] in ids]

    console.print()
    console.print(Panel(
        "[bold cyan]AIops with Claude[/bold cyan]\n"
        "[bold]7 Optimization Techniques for Production LLM Systems[/bold]\n\n"
        "[dim]Each demo shows a before/after comparison with real metrics[/dim]",
        border_style="cyan",
        expand=False,
    ))

    # Overview table
    overview = Table(title="Optimization Techniques", box=box.ROUNDED)
    overview.add_column("#", style="dim", width=3)
    overview.add_column("Technique", style="bold cyan")
    overview.add_column("Description", style="dim")
    overview.add_column("Benefit", style="green")

    for d in DEMOS:
        overview.add_row(d["id"], d["name"], d["description"][:60], d["benefit"])
    console.print(overview)
    console.print()

    # Run demos
    results = []
    for i, demo in enumerate(demos_to_run, 1):
        console.print(Rule(f"[bold cyan]Demo {demo['id']}: {demo['name']}[/bold cyan]"))
        console.print(f"[dim]{demo['description']}[/dim]\n")

        success, elapsed = run_demo(demo)
        results.append({**demo, "success": success, "elapsed": elapsed})

        status = "[green]PASSED[/green]" if success else "[red]FAILED[/red]"
        console.print(f"\n[dim]Result: {status} in {elapsed:.1f}s[/dim]")
        console.print()

    # Summary
    console.print(Rule("[bold]Run Summary[/bold]"))
    summary = Table(title=f"Results ({len(demos_to_run)} demos)", box=box.ROUNDED)
    summary.add_column("Demo", style="cyan")
    summary.add_column("Technique")
    summary.add_column("Status", justify="center")
    summary.add_column("Time", justify="right")
    summary.add_column("Benefit", style="green")

    passed = sum(1 for r in results if r["success"])
    for r in results:
        status = "[green]✓ PASS[/green]" if r["success"] else "[red]✗ FAIL[/red]"
        summary.add_row(
            f"{r['id']} {r['name']}",
            r["technique"],
            status,
            f"{r['elapsed']:.1f}s",
            r["benefit"],
        )
    console.print(summary)

    console.print(Panel(
        f"[bold]Completed:[/bold] {passed}/{len(demos_to_run)} demos passed\n\n"
        "[bold]Key Takeaways:[/bold]\n"
        "• [cyan]Streaming[/cyan] → instant feedback, better UX\n"
        "• [cyan]Structured output[/cyan] → reliable data extraction, no post-processing\n"
        "• [cyan]Tool use[/cyan] → grounded answers, actionable agents\n"
        "• [cyan]Parallel processing[/cyan] → linear scale-out for I/O-bound workloads\n"
        "• [cyan]Model routing[/cyan] → right-size every request\n"
        "• [cyan]Prompt engineering[/cyan] → fewer tokens, faster responses, better output\n"
        "• [cyan]Async batching[/cyan] → combine all techniques for maximum throughput\n\n"
        "[bold]The formula:[/bold] "
        "[green]right model[/green] + [blue]optimized prompt[/blue] + "
        "[yellow]async batching[/yellow] + [cyan]streaming[/cyan] = "
        "[bold]production-grade AIops[/bold]",
        border_style="cyan",
    ))

    sys.exit(0 if passed == len(demos_to_run) else 1)


if __name__ == "__main__":
    main()
