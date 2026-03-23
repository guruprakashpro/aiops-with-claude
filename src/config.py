"""
Central configuration for the AIops project.

- Loads .env file
- Defines system prompts
- Provides model selection logic
"""

import os
from dotenv import load_dotenv
from src.llm_client import FAST_MODEL, SMART_MODEL

load_dotenv()

# ---------------------------------------------------------------------------
# System prompt - used across all AIops modules
# ---------------------------------------------------------------------------
AIOPS_SYSTEM_PROMPT = """You are an expert Site Reliability Engineer (SRE) and DevOps AI assistant with deep knowledge of:
- Distributed systems, microservices, and cloud infrastructure
- Incident response, root cause analysis (RCA), and postmortems
- Observability: metrics, logs, and traces (the three pillars)
- Kubernetes, Docker, AWS/GCP/Azure cloud services
- Common failure patterns: thundering herd, cascading failures, split-brain, resource exhaustion
- Runbook creation and operational best practices
- SLOs, SLAs, error budgets, and reliability engineering

When analyzing incidents or logs, you:
1. Identify the most likely root cause first
2. List affected services and blast radius
3. Suggest immediate mitigation steps (stop the bleeding)
4. Recommend longer-term preventive measures
5. Communicate with clarity and urgency appropriate to the severity

Always structure your responses clearly with sections when appropriate.
Be concise but complete - avoid unnecessary filler words.
When giving severity, use P1 (critical/outage), P2 (major degradation), P3 (minor issue), P4 (informational)."""

# Shorter prompt for simple tasks (saves tokens)
SIMPLE_SYSTEM_PROMPT = """You are an expert SRE AI. Be concise and structured.
Use P1/P2/P3/P4 severity. Focus on actionable insights."""


def select_model(complexity: str) -> str:
    """
    Optimization: Smart model selection routes tasks to the right model.

    Using a fast/cheap model for simple tasks saves cost and latency.
    Using the smart model only when needed maximizes quality where it matters.

    Args:
        complexity: "simple" | "medium" | "complex"

    Returns:
        Model ID string
    """
    routing = {
        "simple": FAST_MODEL,   # llama-3.1-8b-instant: fast, cheap, good for classification
        "medium": FAST_MODEL,   # Still fast model for medium tasks
        "complex": SMART_MODEL, # llama-3.3-70b-versatile: powerful, for deep reasoning
    }
    return routing.get(complexity, SMART_MODEL)


def get_api_key() -> str:
    """Retrieve and validate the Groq API key from environment."""
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise EnvironmentError(
            "GROQ_API_KEY not set. Copy .env.example to .env and add your key."
        )
    return key
