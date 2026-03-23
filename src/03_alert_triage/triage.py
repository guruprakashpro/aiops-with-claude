"""
Alert Triage with Structured Output (JSON Mode)

Optimization: STRUCTURED OUTPUT (JSON MODE)

Instead of parsing free-form text with fragile regex, we instruct the LLM
to respond in strict JSON format. Combined with Pydantic validation, this
gives us:
- Guaranteed field presence
- Type safety
- Easy downstream processing
- No regex maintenance burden

json_mode=True sets response_format={"type": "json_object"} in the API call,
which forces the model to output valid JSON.
"""

import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from typing import Literal
from pydantic import BaseModel, Field
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from src.llm_client import LLMClient, FAST_MODEL
from src.config import select_model

console = Console()
client = LLMClient()


# ---------------------------------------------------------------------------
# Pydantic model for structured triage output
# ---------------------------------------------------------------------------

class AlertTriage(BaseModel):
    """
    Structured result from alert triage.
    All fields are validated by Pydantic - no partial/malformed responses.
    """

    severity: Literal["P1", "P2", "P3", "P4"] = Field(
        description="P1=critical outage, P2=major degradation, P3=minor issue, P4=informational"
    )
    category: str = Field(
        description="Alert category: performance | availability | security | capacity | data"
    )
    summary: str = Field(
        description="One-sentence summary of what is happening"
    )
    suggested_action: str = Field(
        description="The single most important action to take right now"
    )
    escalate_to_human: bool = Field(
        description="Whether this requires immediate human intervention"
    )
    estimated_resolution_minutes: int = Field(
        description="Estimated time to resolve in minutes"
    )
    affected_component: str = Field(
        default="unknown",
        description="Primary component or service affected",
    )
    runbook_hint: str = Field(
        default="",
        description="Which runbook or procedure to follow",
    )


# ---------------------------------------------------------------------------
# Triage functions
# ---------------------------------------------------------------------------

TRIAGE_SYSTEM_PROMPT = """You are an expert SRE alert triage system.
Analyze alerts and classify them quickly and accurately.
Always respond with valid JSON matching the exact schema requested.
Be decisive - if unsure between two severities, pick the higher one (safer)."""


def triage_alert(alert: str) -> AlertTriage:
    """
    Triage a single alert using JSON mode for structured output.

    Optimization: json_mode=True ensures the response is always valid JSON.
    We use FAST_MODEL since triage is a classification task - the small model
    handles it well and it's much faster.

    Args:
        alert: Raw alert text or description

    Returns:
        AlertTriage with validated fields
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
- escalate_to_human: true/false (true for P1/P2 or novel issues)
- estimated_resolution_minutes: integer estimate
- affected_component: primary service or component name
- runbook_hint: brief hint about which runbook or procedure applies

Alert:
{alert}""",
        },
    ]

    # JSON mode guarantees valid JSON output - no need for regex parsing
    raw = client.complete(
        messages,
        model=FAST_MODEL,
        json_mode=True,
        temperature=0.1,  # Low temperature for deterministic classification
    )

    try:
        data = json.loads(raw)
        return AlertTriage(**data)
    except (json.JSONDecodeError, Exception) as e:
        # Fallback for malformed responses (shouldn't happen with json_mode=True)
        console.print(f"[yellow]Warning: Could not parse triage response: {e}[/yellow]")
        return AlertTriage(
            severity="P2",
            category="availability",
            summary="Alert parsing failed - manual review required",
            suggested_action="Review alert manually",
            escalate_to_human=True,
            estimated_resolution_minutes=30,
        )


def batch_triage_sequential(alerts: list[str]) -> list[AlertTriage]:
    """
    Triage a list of alerts one by one (sequential baseline).

    This is the naive approach - each alert waits for the previous one.
    See batch_triage.py for the optimized parallel version.

    Args:
        alerts: List of alert strings

    Returns:
        List of AlertTriage results in same order as input
    """
    results = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            "[cyan]Triaging alerts (sequential)...", total=len(alerts)
        )

        for i, alert in enumerate(alerts):
            progress.update(task, description=f"[cyan]Triaging alert {i+1}/{len(alerts)}...")
            result = triage_alert(alert)
            results.append(result)
            progress.advance(task)

    return results
