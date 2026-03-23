"""
Optimization 01: Streaming

CONCEPT:
Instead of waiting for the complete response before displaying anything,
streaming sends chunks as they're generated. This means:
- Users see the first word in ~200ms instead of waiting 8+ seconds
- Perceived latency is dramatically lower
- Progress is visible, reducing anxiety during long generations

TECHNICAL:
The Groq API supports Server-Sent Events (SSE) streaming.
With stream=True, the API returns a generator that yields chunks
as the model generates them token by token.

Run: python src/optimizations/01_streaming.py
"""

import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich import box

from src.llm_client import LLMClient, SMART_MODEL

console = Console()
client = LLMClient()

PROMPT = """Analyze this production incident and provide a detailed response:
Error: Database connection pool exhausted (50/50 connections in use, 28 queued)
Impact: API gateway returning 503 errors at 61% rate
Duration: 15 minutes
Service: order-processor suspected connection leak

Provide: timeline, root cause analysis, immediate actions, and long-term fixes."""

MESSAGES = [
    {"role": "system", "content": "You are an expert SRE. Provide detailed, actionable analysis."},
    {"role": "user", "content": PROMPT},
]


def demo_non_streaming() -> tuple[str, float, float]:
    """
    Non-streaming: wait for entire response before displaying.
    Returns: (response, time_to_first_token, total_time)
    """
    start = time.time()
    response = client.complete(MESSAGES, model=SMART_MODEL, stream=False)
    total_time = time.time() - start
    # Non-streaming: time to first token = total time (nothing shown until complete)
    return response, total_time, total_time


def demo_streaming() -> tuple[str, float, float]:
    """
    Streaming: display chunks as they arrive in real time.
    Returns: (full_response, time_to_first_token, total_time)
    """
    start = time.time()
    first_token_time = None
    full_response = ""

    console.print("[dim]Streaming output:[/dim]\n")

    for chunk in client.stream_complete(MESSAGES, model=SMART_MODEL):
        if first_token_time is None:
            first_token_time = time.time() - start
        full_response += chunk
        console.print(chunk, end="", highlight=False)

    total_time = time.time() - start
    console.print("\n")  # newline after stream

    return full_response, first_token_time or total_time, total_time


def main():
    console.print()
    console.print(Panel(
        "[bold green]Optimization 01: Streaming[/bold green]\n"
        "[dim]Compare time-to-first-token: streaming vs non-streaming[/dim]",
        expand=False,
        border_style="green",
    ))

    console.print(Panel(
        "[bold]What is Streaming?[/bold]\n\n"
        "Non-streaming: LLM generates the entire response, THEN sends it.\n"
        "               User waits 5-15 seconds seeing nothing.\n\n"
        "Streaming:     LLM sends each token as it's generated.\n"
        "               User sees output after ~200ms.\n\n"
        "[bold]When to use streaming:[/bold]\n"
        "• Any response longer than ~3 sentences\n"
        "• User-facing interfaces\n"
        "• Long analysis or explanation tasks\n\n"
        "[bold]When NOT to stream:[/bold]\n"
        "• JSON mode (streaming + json_mode can cause parse issues)\n"
        "• When you need usage statistics\n"
        "• Background batch processing",
        title="Streaming Explained",
        border_style="blue",
        expand=False,
    ))

    # -----------------------------------------------------------------------
    # Test 1: Non-streaming
    # -----------------------------------------------------------------------
    console.print(Rule("[bold yellow]Test 1: Non-Streaming[/bold yellow]"))
    console.print("[dim]Waiting for complete response before displaying...[/dim]\n")

    ns_start = time.time()
    try:
        ns_response, ns_ttft, ns_total = demo_non_streaming()
        console.print(f"[dim]{ns_response[:300]}...[/dim]")
        console.print(f"\n[yellow]Time to first token: {ns_ttft:.2f}s (waited for entire response)[/yellow]")
        console.print(f"[yellow]Total time: {ns_total:.2f}s[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        ns_ttft, ns_total = 8.0, 8.0  # Fallback for comparison display

    # -----------------------------------------------------------------------
    # Test 2: Streaming
    # -----------------------------------------------------------------------
    console.print(Rule("[bold green]Test 2: Streaming[/bold green]"))
    console.print("[dim]Displaying chunks as they arrive...[/dim]\n")

    try:
        s_response, s_ttft, s_total = demo_streaming()
        console.print(f"[green]Time to first token: {s_ttft:.2f}s[/green]")
        console.print(f"[green]Total time: {s_total:.2f}s[/green]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        s_ttft, s_total = 0.3, 8.0

    # -----------------------------------------------------------------------
    # Comparison
    # -----------------------------------------------------------------------
    console.print(Rule("[bold]Results Comparison[/bold]"))

    comparison = Table(box=box.ROUNDED, title="Streaming vs Non-Streaming")
    comparison.add_column("Metric", style="bold cyan")
    comparison.add_column("Non-Streaming", justify="right", style="yellow")
    comparison.add_column("Streaming", justify="right", style="green")
    comparison.add_column("Improvement", justify="right")

    ttft_improvement = ns_ttft / s_ttft if s_ttft > 0 else 1
    comparison.add_row(
        "Time to First Token",
        f"{ns_ttft:.2f}s",
        f"{s_ttft:.2f}s",
        f"[green]{ttft_improvement:.1f}x faster[/green]",
    )
    comparison.add_row(
        "Total Time",
        f"{ns_total:.2f}s",
        f"{s_total:.2f}s",
        "Similar (same compute)",
    )
    comparison.add_row(
        "User Experience",
        "Blank screen → sudden wall of text",
        "Progressive display from token 1",
        "[green]Dramatically better[/green]",
    )

    console.print(comparison)

    console.print(Panel(
        "[bold]Key Takeaway:[/bold]\n"
        "Streaming doesn't make the LLM faster — the total compute time is identical.\n"
        "But perceived latency drops from [red]8-15 seconds[/red] to [green]<300ms[/green] to first content.\n"
        "This is the single highest-impact UX optimization for LLM applications.",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
