"""
Log Analyzer Module

Optimization: STREAMING + MODEL SELECTION

Key techniques demonstrated:
1. STREAMING - Use stream_complete() to show analysis in real time.
   Users see output immediately rather than waiting 10+ seconds for
   a full response. Dramatically improves perceived performance.

2. MODEL SELECTION - Route tasks to the appropriate model:
   - FAST_MODEL for quick log scanning (pattern matching, classification)
   - SMART_MODEL for deep analysis requiring reasoning across many log lines
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule

from src.llm_client import LLMClient, FAST_MODEL, SMART_MODEL
from src.config import AIOPS_SYSTEM_PROMPT, select_model

console = Console()
client = LLMClient()


def analyze_logs_streaming(logs: list[str]) -> None:
    """
    Analyze logs with STREAMING output for real-time display.

    Optimization: stream_complete() yields chunks as they arrive from the API,
    so the user sees the analysis build up word by word instead of waiting
    for the entire response. This is the single biggest UX improvement
    for long-running LLM calls.

    Uses SMART_MODEL because multi-line log correlation requires reasoning.

    Args:
        logs: List of raw log line strings
    """
    log_block = "\n".join(logs)

    messages = [
        {"role": "system", "content": AIOPS_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""Analyze these server logs and provide:
1. **Timeline Summary** - What happened, in chronological order
2. **Root Cause** - Most likely cause of any errors
3. **Affected Services** - Which services are impacted
4. **Severity** - P1/P2/P3/P4 with justification
5. **Immediate Actions** - What to do right now (ordered by priority)

Logs:
```
{log_block}
```""",
        },
    ]

    console.print(Panel("[bold cyan]Log Analysis (Streaming)[/bold cyan]", expand=False))
    console.print(
        f"[dim]Model: {SMART_MODEL} | Streaming: ON | Lines: {len(logs)}[/dim]\n"
    )

    # Stream the response - chunks arrive in real time
    buffer = ""
    for chunk in client.stream_complete(messages, model=SMART_MODEL):
        console.print(chunk, end="", highlight=False)
        buffer += chunk

    console.print("\n")  # newline after streaming ends


def analyze_metrics(metrics: dict) -> dict:
    """
    Analyze system metrics and return structured findings.

    Uses FAST_MODEL since metric summarization is a pattern-matching task
    that doesn't require deep reasoning - saves latency and cost.

    Args:
        metrics: Dict with metric name -> list of values

    Returns:
        Dict with keys: summary, trend, risk_level, bottleneck
    """
    # Format metrics for the prompt
    metric_summary = []
    for key, values in metrics.items():
        if key == "timestamps":
            continue
        first = values[0]
        last = values[-1]
        peak = max(values) if isinstance(values[0], (int, float)) else values[-1]
        change = ((last - first) / first * 100) if isinstance(first, (int, float)) and first != 0 else 0
        metric_summary.append(
            f"  {key}: start={first}, current={last}, peak={peak}, change={change:+.1f}%"
        )

    metric_text = "\n".join(metric_summary)

    messages = [
        {"role": "system", "content": "You are an SRE analyzing system metrics. Respond in JSON."},
        {
            "role": "user",
            "content": f"""Analyze these metrics and respond with a JSON object containing:
- "summary": one sentence describing what's happening
- "trend": "degrading" | "stable" | "recovering"
- "risk_level": "critical" | "high" | "medium" | "low"
- "bottleneck": the single most likely bottleneck resource or service

Metrics (10 time windows, oldest to newest):
{metric_text}""",
        },
    ]

    # FAST_MODEL is sufficient for structured metric classification
    result_text = client.complete(
        messages, model=FAST_MODEL, json_mode=True, temperature=0.1
    )

    try:
        import json
        return json.loads(result_text)
    except Exception:
        return {
            "summary": result_text,
            "trend": "unknown",
            "risk_level": "unknown",
            "bottleneck": "unknown",
        }


def detect_anomalies(metrics: dict) -> list[str]:
    """
    Detect statistical anomalies in metrics using threshold + LLM analysis.

    Uses FAST_MODEL for efficiency - anomaly detection is mostly
    classification of known patterns.

    Args:
        metrics: Dict with metric name -> list of numeric values

    Returns:
        List of anomaly description strings
    """
    anomalies = []

    # Static threshold checks first (no LLM needed - fast and cheap)
    values_map = {k: v for k, v in metrics.items() if k != "timestamps"}
    thresholds = {
        "cpu_usage": 85.0,
        "memory_usage": 85.0,
        "error_rate": 5.0,
        "latency_p99": 2000,
        "db_connections_active": 45,
    }
    for metric, threshold in thresholds.items():
        if metric in values_map:
            current = values_map[metric][-1]
            if isinstance(current, (int, float)) and current > threshold:
                anomalies.append(
                    f"{metric} is {current} (threshold: {threshold}) - ANOMALY"
                )

    # Use LLM to detect pattern-based anomalies (e.g., correlated spikes)
    # FAST_MODEL handles this well
    metric_lines = []
    for k, v in values_map.items():
        if isinstance(v[0], (int, float)):
            metric_lines.append(f"{k}: {v}")

    messages = [
        {"role": "system", "content": "You are an SRE anomaly detector. Be brief and precise."},
        {
            "role": "user",
            "content": f"""Identify any correlations or anomaly patterns in these metrics (10 time windows).
List each anomaly as a single line. Focus on: sudden changes, correlated spikes, resource exhaustion patterns.
If no additional anomalies, say "No additional pattern anomalies detected."

{chr(10).join(metric_lines)}""",
        },
    ]

    pattern_result = client.complete(messages, model=FAST_MODEL, temperature=0.1)
    for line in pattern_result.strip().split("\n"):
        line = line.strip()
        if line and not line.startswith("No additional"):
            anomalies.append(line)

    return anomalies
