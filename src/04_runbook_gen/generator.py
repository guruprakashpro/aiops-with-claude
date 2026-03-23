"""
Runbook Generator with Prompt Caching Simulation + Token Optimization

Optimization: PROMPT CACHING SIMULATION + TOKEN OPTIMIZATION

Key techniques demonstrated:

1. PROMPT CACHING SIMULATION: Build a rich, reusable system context ONCE and
   reuse it across multiple runbook generations. In production APIs that support
   prompt caching (like Anthropic's), the cached prefix is stored server-side
   and not re-processed. Here we simulate this by pre-building the context
   and measuring token reuse.

2. TOKEN OPTIMIZATION: Compare a "verbose" prompt vs an optimized prompt for
   the same task. Fewer tokens = lower cost + faster responses.

3. RunbookCache: Simple in-memory cache to avoid regenerating runbooks for
   the same incident type. Saves both time and API costs.
"""

import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from typing import Optional
from rich.console import Console

from src.llm_client import LLMClient, SMART_MODEL, FAST_MODEL

console = Console()
client = LLMClient()

# ---------------------------------------------------------------------------
# Rich system context - built ONCE, reused across all generations
# This simulates what would be a cached prompt prefix in production.
# The context includes runbook template, best practices, and standards.
# ---------------------------------------------------------------------------

CACHED_SYSTEM_CONTEXT = """You are an expert SRE runbook author. You create clear, actionable runbooks.

## Runbook Template (follow this structure exactly):
```
# Runbook: [Incident Type]
**Severity:** P1/P2/P3/P4
**Last Updated:** [date]
**Owner:** SRE Team

## Overview
Brief description of what this runbook addresses.

## Detection
How to confirm this issue is occurring (monitoring queries, dashboards).

## Impact Assessment
What services/users are affected and how badly.

## Immediate Response (< 5 minutes)
Step-by-step actions to stop the bleeding, numbered.

## Investigation Steps
How to determine root cause, with specific commands.

## Resolution Procedures
Detailed fix steps, ordered by likelihood of success.

## Escalation
When and who to escalate to.

## Prevention
Long-term fixes to prevent recurrence.

## Post-Incident
Checklist for after resolution.
```

## Company Standards:
- All runbooks must include at least 3 numbered immediate response steps
- Always include specific kubectl/shell commands where applicable
- Include Prometheus/Grafana query examples for detection
- Severity definitions: P1=production outage, P2=degraded service, P3=minor issue, P4=informational
- Escalation path: On-call SRE → SRE Lead → Engineering Manager → VP Engineering
- All commands must be tested and include expected output
- Include rollback steps for any changes made

## Best Practices:
- Be specific: use exact command syntax, not descriptions
- Include expected outputs so engineers know if steps worked
- Order resolution steps by risk (safest first)
- Document any destructive operations with explicit warnings
- Include time estimates for each major section
- Cross-reference related runbooks

## Common Kubectl Commands Reference:
- Check pod status: kubectl get pods -n <namespace> -o wide
- Describe pod: kubectl describe pod <pod-name> -n <namespace>
- Get logs: kubectl logs <pod-name> -n <namespace> --tail=100
- Restart deployment: kubectl rollout restart deployment/<name> -n <namespace>
- Scale deployment: kubectl scale deployment/<name> --replicas=<n> -n <namespace>
- Check resource usage: kubectl top pods -n <namespace>

## Database Operations Reference:
- Kill long queries: SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE duration > interval '30 seconds';
- Check connections: SELECT count(*), state FROM pg_stat_activity GROUP BY state;
- Connection pool stats: SELECT * FROM pg_stat_activity WHERE application_name LIKE 'HikariPool%';
"""

# Token count of the cached context (approximate)
CACHED_CONTEXT_TOKENS = len(CACHED_SYSTEM_CONTEXT.split()) * 1.3  # rough word-to-token ratio


# ---------------------------------------------------------------------------
# RunbookCache - avoids regenerating runbooks for the same incident type
# ---------------------------------------------------------------------------

class RunbookCache:
    """
    Simple in-memory cache for generated runbooks.

    Optimization: Caching identical requests eliminates redundant API calls.
    In a real system this would be backed by Redis or a database.
    """

    def __init__(self):
        self._cache: dict[str, str] = {}
        self._hits: int = 0
        self._misses: int = 0

    def get(self, incident_type: str) -> Optional[str]:
        key = incident_type.lower().strip()
        if key in self._cache:
            self._hits += 1
            return self._cache[key]
        self._misses += 1
        return None

    def set(self, incident_type: str, runbook: str) -> None:
        key = incident_type.lower().strip()
        self._cache[key] = runbook

    def stats(self) -> dict:
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_pct": round(hit_rate, 1),
            "cached_runbooks": len(self._cache),
        }


# Global cache instance
_runbook_cache = RunbookCache()


def generate_runbook(incident_type: str, context: str = "") -> dict:
    """
    Generate a runbook using the CACHED system context.

    The key optimization: CACHED_SYSTEM_CONTEXT is built once and sent
    with every request. In APIs with true prompt caching, this prefix
    is stored server-side after the first call. Subsequent calls with
    the same cached prefix skip reprocessing it, saving time and cost.

    Args:
        incident_type: Type of incident (e.g., "Database connection pool exhausted")
        context: Additional incident-specific context

    Returns:
        Dict with: runbook (str), tokens_used (int), generation_time (float), from_cache (bool)
    """
    # Check application-level cache first
    cached = _runbook_cache.get(incident_type)
    if cached:
        return {
            "runbook": cached,
            "tokens_used": 0,
            "generation_time": 0.001,
            "from_cache": True,
            "prompt_tokens": 0,
        }

    messages = [
        {
            "role": "system",
            # This large system context simulates a cached prompt prefix
            "content": CACHED_SYSTEM_CONTEXT,
        },
        {
            "role": "user",
            "content": (
                f"Generate a complete runbook for: {incident_type}\n"
                + (f"\nAdditional context: {context}" if context else "")
            ),
        },
    ]

    start = time.time()
    runbook_text = client.complete(messages, model=SMART_MODEL, temperature=0.2)
    elapsed = time.time() - start

    usage = client.last_usage
    _runbook_cache.set(incident_type, runbook_text)

    return {
        "runbook": runbook_text,
        "tokens_used": usage.get("total_tokens", 0),
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "generation_time": elapsed,
        "from_cache": False,
    }


def generate_runbook_minimal(incident_type: str) -> dict:
    """
    Generate a runbook with a MINIMAL prompt (no cached context).

    Used for token optimization comparison: shows how much the quality
    and token count differs between a rich context vs minimal prompt.

    Args:
        incident_type: Type of incident

    Returns:
        Dict with: runbook (str), tokens_used (int), generation_time (float)
    """
    messages = [
        {"role": "system", "content": "You are an SRE. Write a runbook."},
        {"role": "user", "content": f"Write a runbook for: {incident_type}"},
    ]

    start = time.time()
    runbook_text = client.complete(messages, model=SMART_MODEL, temperature=0.2)
    elapsed = time.time() - start

    usage = client.last_usage
    return {
        "runbook": runbook_text,
        "tokens_used": usage.get("total_tokens", 0),
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "generation_time": elapsed,
        "from_cache": False,
    }


def get_cache_stats() -> dict:
    """Return current runbook cache statistics."""
    return _runbook_cache.stats()
