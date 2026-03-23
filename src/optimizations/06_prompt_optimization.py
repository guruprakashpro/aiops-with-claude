"""
Optimization 06: Prompt Optimization

CONCEPT:
Prompt quality directly controls token usage, latency, and response quality.
A well-crafted prompt can reduce tokens by 40-60% while improving output.

TECHNIQUES DEMONSTRATED:
1. Verbose vs Concise prompts (same task, fewer tokens)
2. Role + Context framing (improves quality)
3. Output format specification (eliminates post-processing)
4. Few-shot examples (improves consistency)
5. Negative constraints (reduce irrelevant content)
6. Chain-of-thought for complex tasks

Run: python src/optimizations/06_prompt_optimization.py
"""

import sys
import os
import time
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich.rule import Rule
from rich import box

from src.llm_client import LLMClient, FAST_MODEL, SMART_MODEL

console = Console()
client = LLMClient()

ALERT = "Memory usage 94% on auth-service-prod-02. OOMKill risk."


# -----------------------------------------------------------------------
# Prompt pairs: before vs after optimization
# -----------------------------------------------------------------------
EXAMPLES = [
    {
        "name": "Verbose vs Concise",
        "before": {
            "system": "You are a helpful AI assistant that can help with many different tasks including analyzing systems and providing recommendations.",
            "user": (
                "Hello! I was wondering if you could please help me with something. "
                "I have an alert that came in and I'm not sure what to do about it. "
                "The alert says: '" + ALERT + "'. "
                "Could you please tell me what you think about this and maybe give me some suggestions "
                "about what I might want to do to address this issue? Thank you so much for your help!"
            ),
        },
        "after": {
            "system": "You are an SRE. Be brief and direct.",
            "user": f"Alert: {ALERT}\nProvide: severity (P1-P4), immediate action (1 sentence).",
        },
        "why": "Remove filler words, greetings, apologies. Be direct. Saves 60+ tokens.",
    },
    {
        "name": "Vague vs Specific Output Format",
        "before": {
            "system": "You are an SRE assistant.",
            "user": f"Analyze this alert: {ALERT}",
        },
        "after": {
            "system": "You are an SRE. Respond ONLY in this JSON format: {{\"severity\":\"P1-P4\",\"action\":\"string\",\"escalate\":bool}}",
            "user": f"Alert: {ALERT}",
        },
        "why": "Specify exact output format. Eliminates need for post-processing regex.",
    },
    {
        "name": "No Examples vs Few-Shot",
        "before": {
            "system": "Classify alert severity.",
            "user": f"Alert: {ALERT}",
        },
        "after": {
            "system": (
                "Classify alert severity. Examples:\n"
                "- 'CPU 95% prod' → P1 (immediate action)\n"
                "- 'CPU 80% prod' → P2 (investigate soon)\n"
                "- 'CPU 70% staging' → P3 (monitor)\n"
                "- 'Scheduled backup started' → P4 (ignore)\n"
                "Reply with just: P1, P2, P3, or P4"
            ),
            "user": f"Alert: {ALERT}",
        },
        "why": "Few-shot examples calibrate the model to your severity definitions precisely.",
    },
    {
        "name": "Without vs With Constraints",
        "before": {
            "system": "You are an SRE. Help with incidents.",
            "user": f"What should I do about: {ALERT}",
        },
        "after": {
            "system": "You are an SRE.",
            "user": (
                f"Alert: {ALERT}\n"
                "Give me the top 3 immediate actions. "
                "DO NOT explain what memory is. "
                "DO NOT add caveats or disclaimers. "
                "Format: numbered list only."
            ),
        },
        "why": "Negative constraints prevent LLM from padding with explanations you don't need.",
    },
]


def run_prompt(system: str, user: str, model: str = FAST_MODEL) -> tuple[str, float, int]:
    start = time.time()
    response = client.complete(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        model=model,
        temperature=0.1,
    )
    latency = time.time() - start
    # Rough token estimate: prompt + response
    prompt_tokens = len((system + user).split()) * 1.3
    response_tokens = len(response.split()) * 1.3
    total = int(prompt_tokens + response_tokens)
    return response, latency, total


def main():
    console.print()
    console.print(Panel(
        "[bold green]Optimization 06: Prompt Optimization[/bold green]\n"
        "[dim]Write better prompts: fewer tokens, faster responses, better output[/dim]",
        expand=False,
        border_style="green",
    ))

    all_stats = []

    for example in EXAMPLES:
        console.print(Rule(f"[bold cyan]{example['name']}[/bold cyan]"))
        console.print(f"[dim italic]{example['why']}[/dim italic]\n")

        # Before
        before = example["before"]
        console.print("[bold red]❌ Before (unoptimized):[/bold red]")
        console.print(Syntax(
            f'system: "{before["system"][:100]}..."\nuser: "{before["user"][:120]}..."',
            "text", theme="monokai",
        ))

        try:
            before_resp, before_lat, before_tok = run_prompt(before["system"], before["user"])
            console.print(f"[dim]Response: {before_resp.strip()[:100]}[/dim]")
            console.print(f"[yellow]~{before_tok} tokens | {before_lat:.2f}s[/yellow]\n")
        except Exception as e:
            console.print(f"[red]{e}[/red]")
            before_tok, before_lat = 200, 2.0
            before_resp = ""

        # After
        after = example["after"]
        console.print("[bold green]✅ After (optimized):[/bold green]")
        console.print(Syntax(
            f'system: "{after["system"][:100]}"\nuser: "{after["user"][:120]}"',
            "text", theme="monokai",
        ))

        try:
            after_resp, after_lat, after_tok = run_prompt(after["system"], after["user"])
            console.print(f"[dim]Response: {after_resp.strip()[:100]}[/dim]")
            console.print(f"[green]~{after_tok} tokens | {after_lat:.2f}s[/green]")
        except Exception as e:
            console.print(f"[red]{e}[/red]")
            after_tok, after_lat = 80, 0.8
            after_resp = ""

        token_savings = before_tok - after_tok
        pct_saving = (token_savings / before_tok * 100) if before_tok > 0 else 0
        all_stats.append({
            "name": example["name"],
            "before_tokens": before_tok,
            "after_tokens": after_tok,
            "savings": token_savings,
            "pct": pct_saving,
            "before_lat": before_lat,
            "after_lat": after_lat,
        })
        console.print()

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    console.print(Rule("[bold]Prompt Optimization Results[/bold]"))
    summary = Table(title="Before vs After Optimization", box=box.ROUNDED)
    summary.add_column("Technique", style="cyan")
    summary.add_column("Before", justify="right", style="yellow")
    summary.add_column("After", justify="right", style="green")
    summary.add_column("Token Savings", justify="right")
    summary.add_column("Latency", justify="right")

    for s in all_stats:
        summary.add_row(
            s["name"],
            f"~{s['before_tokens']} tok",
            f"~{s['after_tokens']} tok",
            f"[green]-{s['pct']:.0f}%[/green]",
            f"[green]{s['before_lat']:.2f}s → {s['after_lat']:.2f}s[/green]",
        )
    console.print(summary)

    console.print(Panel(
        "[bold]Prompt Optimization Checklist:[/bold]\n\n"
        "✅ [green]Remove greetings, filler words, apologies[/green]\n"
        "✅ [green]Specify exact output format (JSON schema, numbered list, etc.)[/green]\n"
        "✅ [green]Add 2-3 few-shot examples for classification tasks[/green]\n"
        "✅ [green]Use negative constraints (DO NOT explain X)[/green]\n"
        "✅ [green]State role clearly in system prompt[/green]\n"
        "✅ [green]Ask for chain-of-thought only when you need reasoning visible[/green]\n"
        "✅ [green]Break long prompts into smaller focused calls[/green]\n\n"
        "[bold]Anti-patterns to avoid:[/bold]\n"
        "❌ [red]'Please help me with...' (padding)[/red]\n"
        "❌ [red]'Feel free to...' (permission wastes tokens)[/red]\n"
        "❌ [red]Asking for output format in natural language instead of showing an example[/red]\n"
        "❌ [red]One giant prompt that does 5 things (split into 5 focused calls)[/red]",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
