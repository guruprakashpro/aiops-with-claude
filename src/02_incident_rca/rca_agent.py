"""
Root Cause Analysis (RCA) Agent with Tool Use

Optimization: TOOL USE AGENTIC LOOP

The agentic loop works as follows:
1. Send the incident description + available tools to the LLM
2. LLM responds with tool_calls (it wants to gather more information)
3. Execute those tool calls and collect results
4. Append tool results to the conversation history
5. Send back to LLM - it may call more tools or give the final answer
6. Loop until LLM produces a text response (no more tool calls)

This mirrors how a skilled engineer investigates: form a hypothesis,
check dashboards, look at recent deployments, then give a diagnosis.
"""

import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from typing import Optional
from pydantic import BaseModel, Field
from rich.console import Console

from src.llm_client import LLMClient, SMART_MODEL
from src.config import AIOPS_SYSTEM_PROMPT
from src.02_incident_rca.tools import TOOLS, TOOL_FUNCTIONS

console = Console()


# ---------------------------------------------------------------------------
# Pydantic result model
# ---------------------------------------------------------------------------

class RCAResult(BaseModel):
    """Structured output from the RCA agent."""

    root_cause: str = Field(description="The primary root cause of the incident")
    affected_services: list[str] = Field(description="List of affected service names")
    recommended_actions: list[str] = Field(
        description="Ordered list of recommended actions to resolve the incident"
    )
    confidence_score: float = Field(
        ge=0.0, le=1.0, description="Confidence in the root cause (0.0 to 1.0)"
    )
    contributing_factors: list[str] = Field(
        default_factory=list,
        description="Secondary factors that contributed to the incident",
    )
    deployment_related: bool = Field(
        default=False,
        description="Whether a recent deployment likely triggered this incident",
    )


# ---------------------------------------------------------------------------
# RCA Agent
# ---------------------------------------------------------------------------

class RCAAgent:
    """
    Agentic RCA investigator that uses tools to gather information
    before producing a root cause analysis.

    The agent loop continues until the LLM stops calling tools and
    produces a final text answer, which is then parsed into RCAResult.
    """

    MAX_TOOL_ITERATIONS = 8  # Prevent infinite loops

    def __init__(self, verbose: bool = True):
        self.client = LLMClient()
        self.verbose = verbose

    def investigate(self, incident: str) -> RCAResult:
        """
        Run the full agentic RCA investigation.

        Args:
            incident: Plain text description of the incident

        Returns:
            RCAResult with root cause and recommendations
        """
        if self.verbose:
            console.print(f"\n[bold yellow]Starting RCA investigation...[/bold yellow]")

        # Build initial message history
        messages = [
            {
                "role": "system",
                "content": (
                    AIOPS_SYSTEM_PROMPT
                    + "\n\nYou have access to tools to investigate the incident. "
                    "Use them systematically: check service health, look at recent deployments, "
                    "trace the dependency chain. When you have enough information, provide "
                    "your final RCA as a structured analysis."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Investigate this incident and determine the root cause:\n\n{incident}\n\n"
                    "Use the available tools to gather information. After investigation, "
                    "provide your RCA with: root cause, affected services, confidence score (0-1), "
                    "and recommended actions."
                ),
            },
        ]

        tool_call_count = 0
        final_response = ""

        # -----------------------------------------------------------------------
        # Agentic loop: keep going until LLM stops calling tools
        # -----------------------------------------------------------------------
        for iteration in range(self.MAX_TOOL_ITERATIONS):
            response = self.client.client.chat.completions.create(
                model=SMART_MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.2,
            )

            message = response.choices[0].message
            finish_reason = response.choices[0].finish_reason

            # Add the assistant's response to history
            messages.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in (message.tool_calls or [])
                ] or None,
            })

            # If no tool calls, we have the final response
            if finish_reason == "stop" or not message.tool_calls:
                final_response = message.content or ""
                if self.verbose:
                    console.print(
                        f"[dim]Investigation complete after {tool_call_count} tool calls[/dim]"
                    )
                break

            # Execute each tool call the LLM requested
            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                try:
                    func_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    func_args = {}

                if self.verbose:
                    console.print(
                        f"  [cyan]Tool call:[/cyan] {func_name}({', '.join(f'{k}={v}' for k, v in func_args.items())})"
                    )

                # Dispatch to actual tool function
                if func_name in TOOL_FUNCTIONS:
                    tool_result = TOOL_FUNCTIONS[func_name](**func_args)
                else:
                    tool_result = {"error": f"Unknown tool: {func_name}"}

                tool_call_count += 1

                # Feed tool result back into the conversation
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result, indent=2),
                })

        # -----------------------------------------------------------------------
        # Parse the final response into structured RCAResult
        # -----------------------------------------------------------------------
        return self._parse_rca_response(final_response, incident)

    def _parse_rca_response(self, response_text: str, incident: str) -> RCAResult:
        """
        Ask the LLM to convert its free-text RCA into a structured JSON result.
        """
        messages = [
            {
                "role": "system",
                "content": "Extract structured information from this RCA analysis. Respond in JSON only.",
            },
            {
                "role": "user",
                "content": f"""Convert this RCA analysis into a JSON object with these exact fields:
- root_cause (string): the primary root cause
- affected_services (array of strings): service names impacted
- recommended_actions (array of strings): ordered actions to resolve
- confidence_score (float 0.0-1.0): how confident in the root cause
- contributing_factors (array of strings): secondary factors
- deployment_related (boolean): was a recent deployment likely the trigger?

RCA Analysis:
{response_text}

Original incident:
{incident}""",
            },
        ]

        json_text = self.client.complete(
            messages, model=SMART_MODEL, json_mode=True, temperature=0.1
        )

        try:
            data = json.loads(json_text)
            return RCAResult(**data)
        except Exception as e:
            # Fallback if parsing fails
            return RCAResult(
                root_cause=response_text[:500] if response_text else "Unable to determine root cause",
                affected_services=["unknown"],
                recommended_actions=["Manual investigation required"],
                confidence_score=0.3,
            )
