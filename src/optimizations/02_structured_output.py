"""
Optimization 02: Structured Output (JSON Mode)

CONCEPT:
Instead of parsing free-text LLM responses with fragile regex, use JSON mode
to force the model to return valid, schema-conforming JSON every time.

BENEFITS:
- 100% parse reliability (no regex edge cases)
- Type-safe downstream processing via Pydantic
- Consistent field names across every call
- Easier to chain into automation pipelines

TECHNICAL:
Set response_format={"type": "json_object"} in the API call.
The model is constrained to output only valid JSON.
Combine with Pydantic for full type validation.

Run: python src/optimizations/02_structured_output.py
"""

import sys
import os
import json
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from pydantic import BaseModel, ValidationError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich.rule import Rule
from rich import box

from src.llm_client import LLMClient, SMART_MODEL

console = Console()
client = LLMClient()

SAMPLE_ALERT = """
ALERT: High error rate on payment-service
Time: 2024-01-15 14:32:00 UTC
Error rate: 23.4% (normally <0.5%)
Affected endpoints: /api/v2/charge, /api/v2/refund
Recent deployment: payment-service v2.3.1 deployed 12 minutes ago
Error type: NullPointerException in PaymentProcessor.charge()
Impact: ~450 failed transactions in last 10 minutes
"""


# ----- Pydantic model defines the exact shape we want -----
class AlertAnalysis(BaseModel):
    severity: str           # P1 / P2 / P3 / P4
    category: str           # deployment / infrastructure / code / external
    summary: str            # one-sentence summary
    root_cause: str         # likely root cause
    immediate_actions: list[str]   # ordered list of actions
    escalate_to_human: bool
    estimated_resolution_minutes: int
    confidence_score: float  # 0.0 - 1.0


def parse_with_regex(alert: str) -> dict:
    """
    Old approach: try to parse LLM free-text with regex.
    Fragile, breaks on any formatting variation.
    """
    response = client.complete(
        messages=[
            {"role": "system", "content": "You are an SRE. Analyze alerts."},
            {"role": "user", "content": f"Analyze this alert and tell me: severity, category, root cause, and immediate actions.\n\n{alert}"},
        ],
        model=SMART_MODEL,
        temperature=0.1,
    )

    # Fragile regex parsing
    result = {}
    severity_match = re.search(r"(P[1-4]|severity[:\s]+(\w+))", response, re.IGNORECASE)
    result["severity"] = severity_match.group(0) if severity_match else "UNKNOWN"

    actions = re.findall(r"(?:\d+\.|[-•])\s*(.+)", response)
    result["actions"] = actions[:3] if actions else ["Could not parse"]
    result["raw"] = response[:300]

    return result


def parse_with_json_mode(alert: str) -> AlertAnalysis:
    """
    New approach: JSON mode + Pydantic validation.
    Reliable, type-safe, schema-enforced.
    """
    schema_hint = """{
  "severity": "P1|P2|P3|P4",
  "category": "deployment|infrastructure|code|external",
  "summary": "one sentence",
  "root_cause": "likely cause",
  "immediate_actions": ["action1", "action2"],
  "escalate_to_human": true|false,
  "estimated_resolution_minutes": 30,
  "confidence_score": 0.85
}"""

    response = client.complete(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert SRE. Analyze alerts and respond ONLY with valid JSON "
                    f"matching this exact schema:\n{schema_hint}"
                ),
            },
            {"role": "user", "content": f"Analyze this alert:\n\n{alert}"},
        ],
        model=SMART_MODEL,
        json_mode=True,
        temperature=0.1,
    )

    data = json.loads(response)
    return AlertAnalysis(**data)


def main():
    console.print()
    console.print(Panel(
        "[bold green]Optimization 02: Structured Output (JSON Mode)[/bold green]\n"
        "[dim]Reliable parsing vs fragile regex[/dim]",
        expand=False,
        border_style="green",
    ))

    console.print(Panel(
        SAMPLE_ALERT.strip(),
        title="[bold]Sample Alert[/bold]",
        border_style="yellow",
    ))

    # -----------------------------------------------------------------------
    # Approach 1: Regex parsing (old way)
    # -----------------------------------------------------------------------
    console.print(Rule("[bold yellow]Approach 1: Free Text + Regex Parsing[/bold yellow]"))
    console.print("[dim]Sending prompt without JSON constraint, then parsing output...[/dim]\n")

    try:
        regex_result = parse_with_regex(SAMPLE_ALERT)

        console.print("[bold red]Problems with this approach:[/bold red]")
        issues = Table(box=box.SIMPLE, show_header=False)
        issues.add_column("Issue", style="red")
        issues.add_column("Example")
        issues.add_row("Unpredictable format", "LLM may say 'P1', 'Priority 1', 'Critical', 'CRITICAL'")
        issues.add_row("Regex brittleness", "Works until LLM changes phrasing, then silently fails")
        issues.add_row("Missing fields", "No guarantee all required fields are present")
        issues.add_row("Type errors", "Numbers may be returned as strings or omitted entirely")
        console.print(issues)

        console.print(f"\n[dim]Parsed result (best effort):[/dim]")
        console.print(f"  Severity: [yellow]{regex_result.get('severity', '???')}[/yellow]")
        console.print(f"  Actions found: {len(regex_result.get('actions', []))}")
        console.print(f"  [red]Structured fields missing, escalate_to_human unknown, confidence unknown[/red]")

    except Exception as e:
        console.print(f"[red]Parsing failed: {e}[/red]")

    # -----------------------------------------------------------------------
    # Approach 2: JSON mode + Pydantic
    # -----------------------------------------------------------------------
    console.print(Rule("[bold green]Approach 2: JSON Mode + Pydantic Validation[/bold green]"))
    console.print("[dim]Using json_mode=True, then validating with Pydantic model...[/dim]\n")

    try:
        result = parse_with_json_mode(SAMPLE_ALERT)

        # Show the clean parsed result
        result_table = Table(title="Parsed AlertAnalysis", box=box.ROUNDED)
        result_table.add_column("Field", style="bold cyan")
        result_table.add_column("Value", style="green")
        result_table.add_column("Type", style="dim")

        result_table.add_row("severity", result.severity, "str")
        result_table.add_row("category", result.category, "str")
        result_table.add_row("summary", result.summary[:60] + "...", "str")
        result_table.add_row("root_cause", result.root_cause[:60] + "...", "str")
        result_table.add_row("immediate_actions", f"{len(result.immediate_actions)} actions", "list[str]")
        result_table.add_row("escalate_to_human", str(result.escalate_to_human), "bool ✓")
        result_table.add_row("estimated_resolution_minutes", str(result.estimated_resolution_minutes), "int ✓")
        result_table.add_row("confidence_score", f"{result.confidence_score:.2f}", "float ✓")
        console.print(result_table)

        console.print("\n[bold]Immediate Actions:[/bold]")
        for i, action in enumerate(result.immediate_actions, 1):
            console.print(f"  {i}. {action}")

        # Show raw JSON
        raw_json = json.dumps(result.model_dump(), indent=2)
        console.print("\n[bold]Raw JSON (machine-readable for automation):[/bold]")
        console.print(Syntax(raw_json, "json", theme="monokai", line_numbers=False))

        # Show usage
        usage = client.get_usage_summary()
        console.print(f"\n[dim]Tokens used: {usage['last_call'].get('total_tokens', 'N/A')}[/dim]")

    except ValidationError as e:
        console.print(f"[red]Pydantic validation failed: {e}[/red]")
    except json.JSONDecodeError as e:
        console.print(f"[red]JSON parse failed: {e}[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    console.print(Rule("[bold]Summary[/bold]"))
    summary = Table(box=box.ROUNDED, title="Regex vs JSON Mode")
    summary.add_column("Aspect", style="bold")
    summary.add_column("Regex Parsing", style="yellow", justify="center")
    summary.add_column("JSON Mode + Pydantic", style="green", justify="center")

    summary.add_row("Parse reliability", "~60-80%", "~99%")
    summary.add_row("Type safety", "❌ None", "✅ Full")
    summary.add_row("Schema enforcement", "❌ Hope for the best", "✅ Guaranteed")
    summary.add_row("Missing field handling", "❌ Silent failure", "✅ Validation error")
    summary.add_row("Automation-ready", "❌ Fragile", "✅ Robust")
    summary.add_row("Maintenance burden", "High (regex upkeep)", "Low (schema update)")
    console.print(summary)

    console.print(Panel(
        "[bold]Key Takeaway:[/bold]\n"
        "Always use JSON mode when you need structured output for downstream processing.\n"
        "Combine with Pydantic models for type safety and clear contracts between\n"
        "your LLM calls and the rest of your application code.",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
