"""
Optimization 03: Tool Use / Function Calling

CONCEPT:
Tool use lets the LLM call your functions to fetch real data before answering.
Instead of the LLM hallucinating system state, it asks YOUR code for facts.

FLOW:
1. You define tools (functions + JSON schema)
2. LLM decides which tools to call and with what arguments
3. Your code executes the tools and returns results
4. LLM uses real results to give a grounded answer

BENEFITS:
- Grounded answers based on real data, not hallucinations
- LLM can take actions (restart service, scale pods, page on-call)
- Separates reasoning (LLM) from execution (your code)
- Auditable: every tool call is logged

Run: python src/optimizations/03_tool_use.py
"""

import sys
import os
import json
import random
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich.syntax import Syntax
from rich import box

from src.llm_client import LLMClient, SMART_MODEL

console = Console()
client = LLMClient()

# -----------------------------------------------------------------------
# Tool definitions (JSON schema for the LLM)
# -----------------------------------------------------------------------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_service_metrics",
            "description": "Get current CPU, memory, error rate and latency metrics for a service",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name": {"type": "string", "description": "Name of the service"},
                    "window_minutes": {"type": "integer", "description": "Time window in minutes", "default": 5},
                },
                "required": ["service_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_deployments",
            "description": "List recent deployments for a service in the past N hours",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name": {"type": "string"},
                    "hours": {"type": "integer", "default": 2},
                },
                "required": ["service_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_dependent_services",
            "description": "Get list of services that this service depends on",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name": {"type": "string"},
                },
                "required": ["service_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_database_connections",
            "description": "Check current DB connection pool usage for a service",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name": {"type": "string"},
                },
                "required": ["service_name"],
            },
        },
    },
]


# -----------------------------------------------------------------------
# Tool implementations (mock data simulating real infrastructure)
# -----------------------------------------------------------------------
def get_service_metrics(service_name: str, window_minutes: int = 5) -> dict:
    mock = {
        "order-service": {"cpu": 87.3, "memory": 91.2, "error_rate": 14.7, "latency_p99_ms": 3200},
        "payment-service": {"cpu": 42.1, "memory": 58.0, "error_rate": 0.3, "latency_p99_ms": 180},
        "auth-service": {"cpu": 23.5, "memory": 41.0, "error_rate": 0.1, "latency_p99_ms": 45},
        "redis-cache": {"cpu": 78.9, "memory": 95.4, "error_rate": 2.1, "latency_p99_ms": 890},
    }
    metrics = mock.get(service_name, {"cpu": random.uniform(20, 60), "memory": random.uniform(30, 70),
                                       "error_rate": random.uniform(0, 2), "latency_p99_ms": random.randint(50, 300)})
    return {"service": service_name, "window_minutes": window_minutes, "metrics": metrics}


def get_recent_deployments(service_name: str, hours: int = 2) -> dict:
    mock = {
        "order-service": [
            {"version": "v3.2.1", "deployed_at": "2024-01-15T14:20:00Z", "by": "ci-pipeline", "status": "success"},
            {"version": "v3.2.0", "deployed_at": "2024-01-15T10:05:00Z", "by": "ci-pipeline", "status": "success"},
        ],
        "redis-cache": [],
    }
    deployments = mock.get(service_name, [])
    return {"service": service_name, "hours": hours, "deployments": deployments}


def get_dependent_services(service_name: str) -> dict:
    deps = {
        "order-service": ["payment-service", "redis-cache", "postgres-primary", "auth-service"],
        "payment-service": ["stripe-api", "postgres-primary", "fraud-detection"],
        "auth-service": ["redis-cache", "postgres-primary"],
    }
    return {"service": service_name, "depends_on": deps.get(service_name, [])}


def check_database_connections(service_name: str) -> dict:
    mock = {
        "order-service": {"pool_size": 20, "active": 19, "idle": 1, "waiting": 12, "max_wait_ms": 5400},
        "payment-service": {"pool_size": 10, "active": 3, "idle": 7, "waiting": 0, "max_wait_ms": 0},
    }
    return mock.get(service_name, {"pool_size": 10, "active": 2, "idle": 8, "waiting": 0, "max_wait_ms": 0})


TOOL_FUNCTIONS = {
    "get_service_metrics": get_service_metrics,
    "get_recent_deployments": get_recent_deployments,
    "get_dependent_services": get_dependent_services,
    "check_database_connections": check_database_connections,
}


def execute_tool(name: str, args: dict) -> str:
    fn = TOOL_FUNCTIONS.get(name)
    if not fn:
        return json.dumps({"error": f"Unknown tool: {name}"})
    result = fn(**args)
    return json.dumps(result, indent=2)


# -----------------------------------------------------------------------
# Agentic tool-use loop
# -----------------------------------------------------------------------
def investigate_with_tools(incident: str) -> str:
    """
    Full tool-use agentic loop:
    1. Send incident + tools to LLM
    2. Execute any tool calls the LLM requests
    3. Send results back
    4. Repeat until LLM gives final answer (no more tool calls)
    """
    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert SRE investigating a production incident. "
                "Use the available tools to gather real metrics and data before drawing conclusions. "
                "Always check metrics, recent deployments, and dependencies before giving your final analysis."
            ),
        },
        {"role": "user", "content": f"Investigate this incident: {incident}"},
    ]

    tool_call_log = []
    iteration = 0
    max_iterations = 8

    while iteration < max_iterations:
        iteration += 1
        console.print(f"  [dim]→ LLM call #{iteration}...[/dim]")

        response = client.client.chat.completions.create(
            model=SMART_MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.1,
        )

        msg = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        # Add assistant message to history
        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in (msg.tool_calls or [])
            ] or None,
        })

        # If no tool calls, LLM is done
        if finish_reason == "stop" or not msg.tool_calls:
            return msg.content or ""

        # Execute each tool call
        for tool_call in msg.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments)

            console.print(f"    [cyan]🔧 Tool call:[/cyan] [bold]{fn_name}[/bold]({', '.join(f'{k}={v}' for k,v in fn_args.items())})")

            result = execute_tool(fn_name, fn_args)
            tool_call_log.append({"tool": fn_name, "args": fn_args, "result": json.loads(result)})

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

    return "Max iterations reached."


def main():
    console.print()
    console.print(Panel(
        "[bold green]Optimization 03: Tool Use / Function Calling[/bold green]\n"
        "[dim]Ground LLM answers in real system data via tool calls[/dim]",
        expand=False,
        border_style="green",
    ))

    console.print(Panel(
        "[bold]Available Tools:[/bold]\n"
        "• [cyan]get_service_metrics[/cyan]      — CPU, memory, error rate, latency\n"
        "• [cyan]get_recent_deployments[/cyan]   — Recent deploys with version + timestamp\n"
        "• [cyan]get_dependent_services[/cyan]   — Upstream/downstream dependencies\n"
        "• [cyan]check_database_connections[/cyan] — DB pool usage and wait times\n\n"
        "[bold]The LLM decides:[/bold] which tools to call, in what order, with what arguments.",
        title="Tool Registry",
        border_style="blue",
        expand=False,
    ))

    incident = (
        "order-service is returning HTTP 503 errors for 18% of requests. "
        "Started about 25 minutes ago. Customers are unable to place orders."
    )

    console.print(Panel(
        f"[bold yellow]{incident}[/bold yellow]",
        title="Incident",
        border_style="yellow",
    ))

    console.print(Rule("[bold]Running Tool-Use Investigation[/bold]"))
    console.print("[dim]Watch the LLM call tools to gather data before answering...[/dim]\n")

    try:
        start = time.time()
        analysis = investigate_with_tools(incident)
        elapsed = time.time() - start

        console.print(Panel(
            analysis,
            title="[bold green]LLM Analysis (Grounded in Real Data)[/bold green]",
            border_style="green",
        ))
        console.print(f"[dim]Completed in {elapsed:.1f}s[/dim]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

    # -----------------------------------------------------------------------
    # Show the concept diagram
    # -----------------------------------------------------------------------
    console.print(Rule("[bold]How Tool Use Works[/bold]"))
    diagram = """
  USER: "Investigate order-service 503s"
        │
        ▼
  [LLM] "I need metrics first"
  ──────────────────────────────────────────
  Tool call: get_service_metrics("order-service")
        │
        ▼ YOUR CODE executes
  {"cpu": 87.3, "error_rate": 14.7, ...}
        │
        ▼
  [LLM] "High CPU. Check deployments"
  ──────────────────────────────────────────
  Tool call: get_recent_deployments("order-service")
        │
        ▼ YOUR CODE executes
  {"deployments": [{"version": "v3.2.1", ...}]}
        │
        ▼
  [LLM] "Deployment 25min ago. Check DB connections"
  ──────────────────────────────────────────
  Tool call: check_database_connections("order-service")
        │
        ▼ YOUR CODE executes
  {"active": 19, "waiting": 12, "max_wait_ms": 5400}
        │
        ▼
  [LLM] Final answer: "Root cause is DB connection pool exhaustion,
        triggered by connection leak in v3.2.1. Rollback immediately."
"""
    console.print(Panel(diagram, title="Tool Use Flow", border_style="blue"))

    console.print(Panel(
        "[bold]Key Takeaway:[/bold]\n"
        "Tool use transforms the LLM from a [red]hallucination machine[/red] into a\n"
        "[green]reasoning engine that acts on real data[/green].\n\n"
        "The LLM handles: [cyan]what to check, reasoning, synthesis[/cyan]\n"
        "Your code handles: [cyan]actual data access, action execution[/cyan]\n\n"
        "This separation of concerns is the foundation of reliable AIops agents.",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
