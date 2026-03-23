"""
Tool definitions for Incident Root Cause Analysis (RCA) agent.

Optimization: TOOL USE / FUNCTION CALLING

The LLM can call these tools to gather real-time information during
investigation, just like a human engineer would check dashboards and
deployment history. This allows the agent to make data-driven decisions
rather than guessing from the incident description alone.
"""

import random
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Tool implementations (mock data simulating real infrastructure APIs)
# ---------------------------------------------------------------------------

def check_service_health(service_name: str) -> dict:
    """
    Returns mock health status for a service.
    In production this would call your monitoring API (Datadog, PagerDuty, etc.)
    """
    health_data = {
        "api-gateway": {
            "status": "degraded",
            "error_rate_pct": 61.4,
            "latency_p99_ms": 12400,
            "instances": {"healthy": 2, "unhealthy": 3, "total": 5},
            "last_restart": "2025-01-15T10:23:00Z",
            "version": "v2.4.1",
        },
        "auth-service": {
            "status": "degraded",
            "error_rate_pct": 22.1,
            "latency_p99_ms": 3400,
            "instances": {"healthy": 3, "unhealthy": 1, "total": 4},
            "last_restart": "2025-01-15T09:00:00Z",
            "version": "v1.8.3",
        },
        "db-pool": {
            "status": "critical",
            "error_rate_pct": 45.2,
            "latency_p99_ms": 5000,
            "connections_active": 50,
            "connections_max": 50,
            "connections_queued": 28,
            "instances": {"healthy": 0, "unhealthy": 1, "total": 1},
            "version": "HikariCP-5.0.1",
        },
        "cache-service": {
            "status": "warning",
            "error_rate_pct": 0.8,
            "latency_p99_ms": 45,
            "memory_usage_pct": 87.1,
            "eviction_rate": 1240,
            "instances": {"healthy": 3, "unhealthy": 0, "total": 3},
            "version": "Redis-7.2.0",
        },
        "order-processor": {
            "status": "critical",
            "error_rate_pct": 89.2,
            "latency_p99_ms": 30100,
            "connection_leak_suspected": True,
            "instances": {"healthy": 0, "unhealthy": 2, "total": 2},
            "version": "v3.1.0",
            "notes": "Long-running queries detected (>30s), possible connection leak",
        },
    }
    return health_data.get(
        service_name,
        {
            "status": "unknown",
            "error_rate_pct": 0.0,
            "latency_p99_ms": 0,
            "instances": {"healthy": 1, "unhealthy": 0, "total": 1},
            "version": "unknown",
        },
    )


def get_recent_deployments(hours: int = 24) -> list:
    """
    Returns mock recent deployments within the last N hours.
    In production this would call your CI/CD system (ArgoCD, Spinnaker, etc.)
    """
    now = datetime.now()
    return [
        {
            "service": "order-processor",
            "version": "v3.1.0",
            "previous_version": "v3.0.8",
            "deployed_at": (now - timedelta(hours=2, minutes=15)).isoformat(),
            "deployed_by": "ci-bot",
            "status": "success",
            "commit": "a3f9c12",
            "commit_message": "feat: optimize batch order processing with connection pooling changes",
            "changed_files": ["src/db/connection_pool.py", "config/hikari.properties"],
        },
        {
            "service": "cache-service",
            "version": "v2.1.1",
            "previous_version": "v2.1.0",
            "deployed_at": (now - timedelta(hours=6)).isoformat(),
            "deployed_by": "jane.doe",
            "status": "success",
            "commit": "b8e2d44",
            "commit_message": "fix: update eviction policy to LRU",
            "changed_files": ["config/redis.conf"],
        },
        {
            "service": "api-gateway",
            "version": "v2.4.1",
            "previous_version": "v2.4.0",
            "deployed_at": (now - timedelta(hours=18)).isoformat(),
            "deployed_by": "john.smith",
            "status": "success",
            "commit": "c1a7b92",
            "commit_message": "chore: update rate limiting thresholds",
            "changed_files": ["config/rate_limits.yaml"],
        },
    ]


def get_error_rate(service: str, minutes: int = 10) -> float:
    """
    Returns mock current error rate for a service.
    In production this would query Prometheus/Datadog metrics API.
    """
    error_rates = {
        "api-gateway": 61.4,
        "auth-service": 22.1,
        "db-pool": 45.2,
        "cache-service": 0.8,
        "order-processor": 89.2,
        "payment-service": 0.2,
        "notification-service": 0.1,
    }
    base = error_rates.get(service, 0.0)
    # Add slight randomness to simulate real metric jitter
    jitter = random.uniform(-1.0, 1.0)
    return round(max(0.0, base + jitter), 2)


def get_dependency_map(service: str) -> dict:
    """
    Returns mock service dependency map (upstream/downstream).
    In production this would query your service mesh (Istio, Linkerd) or CMDB.
    """
    dependency_maps = {
        "api-gateway": {
            "upstream_callers": ["load-balancer", "cdn"],
            "downstream_dependencies": ["auth-service", "order-processor", "cache-service"],
            "critical_path": True,
            "slo_target_pct": 99.9,
        },
        "auth-service": {
            "upstream_callers": ["api-gateway", "mobile-app"],
            "downstream_dependencies": ["db-pool", "cache-service"],
            "critical_path": True,
            "slo_target_pct": 99.95,
        },
        "order-processor": {
            "upstream_callers": ["api-gateway", "batch-job"],
            "downstream_dependencies": ["db-pool", "payment-service", "notification-service"],
            "critical_path": True,
            "slo_target_pct": 99.9,
        },
        "db-pool": {
            "upstream_callers": ["auth-service", "order-processor", "report-service"],
            "downstream_dependencies": ["postgres-primary", "postgres-replica"],
            "critical_path": True,
            "slo_target_pct": 99.99,
        },
        "cache-service": {
            "upstream_callers": ["api-gateway", "auth-service", "order-processor"],
            "downstream_dependencies": [],
            "critical_path": False,
            "slo_target_pct": 99.5,
        },
    }
    return dependency_maps.get(
        service,
        {
            "upstream_callers": [],
            "downstream_dependencies": [],
            "critical_path": False,
            "slo_target_pct": 99.0,
        },
    )


# ---------------------------------------------------------------------------
# TOOLS list - JSON schema definitions for Groq function calling
# ---------------------------------------------------------------------------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_service_health",
            "description": (
                "Check the current health status of a service including error rate, "
                "latency, and instance health. Use this to understand how badly a "
                "service is affected."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": (
                            "Name of the service to check. Valid services: "
                            "api-gateway, auth-service, db-pool, cache-service, order-processor"
                        ),
                    }
                },
                "required": ["service_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_deployments",
            "description": (
                "Get a list of recent deployments. Use this to correlate incident "
                "timing with code changes - a deployment shortly before an incident "
                "is often the root cause."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "hours": {
                        "type": "integer",
                        "description": "How many hours back to look for deployments (default: 24)",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_error_rate",
            "description": (
                "Get the current error rate percentage for a specific service "
                "over the last N minutes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Service name to check error rate for",
                    },
                    "minutes": {
                        "type": "integer",
                        "description": "Time window in minutes (default: 10)",
                    },
                },
                "required": ["service"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_dependency_map",
            "description": (
                "Get the upstream callers and downstream dependencies for a service. "
                "Critical for understanding blast radius and cascading failure paths."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Service name to get dependency map for",
                    }
                },
                "required": ["service"],
            },
        },
    },
]

# Tool dispatch map for the agent loop
TOOL_FUNCTIONS = {
    "check_service_health": check_service_health,
    "get_recent_deployments": get_recent_deployments,
    "get_error_rate": get_error_rate,
    "get_dependency_map": get_dependency_map,
}
