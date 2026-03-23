"""
Anomaly Detector with Multi-Turn Conversation + Context Management

Optimization: MULTI-TURN CONVERSATION + CONTEXT MANAGEMENT

Key techniques:
1. CONVERSATION HISTORY: Maintain rolling conversation history so the LLM
   can reference previous observations when analyzing new data. This enables
   trend detection ("this is worse than 5 minutes ago") that's impossible
   with stateless single-turn calls.

2. CONTEXT MANAGEMENT: Token limits mean you can't keep all history forever.
   _trim_history() keeps only the last N turns, preventing context overflow
   while preserving enough history for meaningful trend analysis.

3. ITERATIVE ANALYSIS: The analyst can ask follow-up questions about
   anomalies, drilling down into specific concerns without restarting context.
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

console = Console()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class AnomalyReport(BaseModel):
    """Structured anomaly detection result for one metrics snapshot."""

    anomalies: list[str] = Field(
        description="List of detected anomalies, each as a descriptive string"
    )
    severity: str = Field(
        description="Overall severity: critical | high | medium | low | normal"
    )
    trend: str = Field(
        description="Trend direction: worsening | stable | improving | unknown"
    )
    prediction: str = Field(
        description="Prediction of what will happen next if no action is taken"
    )
    action_required: bool = Field(
        description="Whether immediate action is required"
    )
    key_metric: str = Field(
        default="",
        description="The single metric most indicative of the issue",
    )
    estimated_time_to_breach: Optional[str] = Field(
        default=None,
        description="Estimated time before a critical threshold is breached",
    )


# ---------------------------------------------------------------------------
# Anomaly Detector
# ---------------------------------------------------------------------------

class AnomalyDetector:
    """
    Stateful anomaly detector that maintains conversation history.

    Each call to analyze() appends to the conversation, allowing the LLM
    to compare current metrics against previously seen values and identify
    trends that span multiple time windows.
    """

    MAX_HISTORY_TURNS = 6  # Keep last 3 user+assistant pairs (6 messages)
    # At ~500 tokens per turn, 6 turns ≈ 3000 tokens of history

    def __init__(self):
        self.client = LLMClient()
        self.conversation_history: list[dict] = []
        self._snapshot_count: int = 0

    def analyze(self, metrics_snapshot: dict) -> AnomalyReport:
        """
        Analyze a metrics snapshot, building on previous conversation context.

        Each call adds to the conversation history, so the LLM can say things
        like "compared to 5 minutes ago, CPU has increased by 15%" which is
        only possible with multi-turn context.

        Args:
            metrics_snapshot: Dict of metric_name -> current_value

        Returns:
            AnomalyReport with detected anomalies and predictions
        """
        self._snapshot_count += 1

        # Format metrics for the prompt
        metric_lines = []
        for k, v in metrics_snapshot.items():
            if k != "timestamp":
                metric_lines.append(f"  {k}: {v}")
        metrics_text = "\n".join(metric_lines)

        # Build the user message for this snapshot
        user_message = {
            "role": "user",
            "content": (
                f"[Snapshot #{self._snapshot_count} - {metrics_snapshot.get('timestamp', 'T+' + str(self._snapshot_count * 5) + 'min')}]\n"
                f"Analyze these metrics for anomalies. Compare with previous snapshots if available.\n\n"
                f"Current metrics:\n{metrics_text}\n\n"
                f"Respond with JSON containing:\n"
                f"- anomalies: list of detected anomalies (empty list if none)\n"
                f"- severity: 'critical'|'high'|'medium'|'low'|'normal'\n"
                f"- trend: 'worsening'|'stable'|'improving'|'unknown'\n"
                f"- prediction: what happens next if no action taken\n"
                f"- action_required: true/false\n"
                f"- key_metric: the most concerning metric name\n"
                f"- estimated_time_to_breach: estimated time before critical threshold breach (or null)"
            ),
        }

        # Add to history
        self.conversation_history.append(user_message)

        # Trim old history to stay within token budget
        self._trim_history()

        # Build full message list: system prompt + conversation history
        messages = [
            {
                "role": "system",
                "content": (
                    AIOPS_SYSTEM_PROMPT
                    + "\n\nYou are monitoring system metrics over time. "
                    "You have memory of previous snapshots in this conversation. "
                    "Always compare current readings to previous ones when making assessments. "
                    "Respond in valid JSON."
                ),
            }
        ] + self.conversation_history

        # Get analysis
        raw = self.client.complete(
            messages,
            model=SMART_MODEL,
            json_mode=True,
            temperature=0.1,
        )

        # Parse and add assistant response to history
        assistant_message = {"role": "assistant", "content": raw}
        self.conversation_history.append(assistant_message)

        try:
            data = json.loads(raw)
            return AnomalyReport(**data)
        except Exception as e:
            console.print(f"[yellow]Warning: could not parse anomaly report: {e}[/yellow]")
            return AnomalyReport(
                anomalies=["Parse error - manual review needed"],
                severity="unknown",
                trend="unknown",
                prediction="Unable to predict",
                action_required=True,
            )

    def follow_up(self, question: str) -> str:
        """
        Ask a follow-up question about the anomalies, using conversation context.

        This is only possible because we maintain conversation history.
        The LLM can reference specific metrics, trends, or anomalies it
        identified in previous turns.

        Args:
            question: Follow-up question about the anomalies

        Returns:
            LLM's answer as a string
        """
        user_message = {"role": "user", "content": question}
        self.conversation_history.append(user_message)

        messages = [
            {
                "role": "system",
                "content": (
                    AIOPS_SYSTEM_PROMPT
                    + " You are in an ongoing analysis conversation. "
                    "Reference your previous observations when answering."
                ),
            }
        ] + self.conversation_history

        response = self.client.complete(messages, model=SMART_MODEL, temperature=0.3)

        self.conversation_history.append({"role": "assistant", "content": response})
        self._trim_history()

        return response

    def _trim_history(self) -> None:
        """
        Context management: trim conversation history to stay under token limit.

        Strategy: Keep the last MAX_HISTORY_TURNS messages.
        This preserves recent context while preventing context window overflow.

        Alternative strategies (not implemented here):
        - Summarize old turns before dropping them
        - Keep only anomaly-containing turns
        - Use token counting to make precise cuts
        """
        if len(self.conversation_history) > self.MAX_HISTORY_TURNS:
            # Drop the oldest messages (keep most recent turns)
            trimmed_count = len(self.conversation_history) - self.MAX_HISTORY_TURNS
            self.conversation_history = self.conversation_history[trimmed_count:]

    def reset(self) -> None:
        """Clear conversation history to start fresh."""
        self.conversation_history = []
        self._snapshot_count = 0

    def history_length(self) -> int:
        """Return current number of messages in history."""
        return len(self.conversation_history)
