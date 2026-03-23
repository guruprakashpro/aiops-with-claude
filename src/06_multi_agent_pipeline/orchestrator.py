"""
AIops Multi-Agent Pipeline Orchestrator

Optimization: FULL PIPELINE - orchestrates all modules

This is the culmination of the project: a full AIops pipeline that chains
all the optimization techniques together:

1. Log ingestion → Anomaly detection (streaming + model selection)
2. If anomaly → Alert triage (structured output + parallel)
3. If P1/P2 → RCA investigation (tool use agentic loop)
4. Generate runbook (prompt caching)
5. Produce incident report (multi-turn context)

Each stage passes structured data to the next, creating an automated
incident response pipeline.
"""

import sys
import os
import uuid
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from datetime import datetime
from pydantic import BaseModel, Field
from rich.console import Console

from src.llm_client import LLMClient, SMART_MODEL, FAST_MODEL
from src.config import AIOPS_SYSTEM_PROMPT
from src.01_log_analysis.analyzer import analyze_metrics, detect_anomalies
from src.02_incident_rca.rca_agent import RCAAgent, RCAResult
from src.03_alert_triage.triage import triage_alert, AlertTriage
from src.04_runbook_gen.generator import generate_runbook
from src.05_anomaly_detection.detector import AnomalyDetector

console = Console()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class IncidentReport(BaseModel):
    """Full incident report produced by the AIops pipeline."""

    incident_id: str = Field(description="Unique incident identifier")
    severity: str = Field(description="P1/P2/P3/P4")
    timestamp: str = Field(description="ISO timestamp when incident was detected")

    anomalies: list[str] = Field(
        description="List of detected anomalies that triggered this incident"
    )
    root_cause: str = Field(description="Root cause determined by RCA agent")
    affected_services: list[str] = Field(description="Services impacted")

    runbook_steps: list[str] = Field(
        description="Key runbook steps extracted from generated runbook"
    )
    resolution_time_estimate: str = Field(
        description="Estimated time to resolve"
    )
    actions_taken: list[str] = Field(
        description="Actions taken by the pipeline (automated + recommended)"
    )

    triage_result: dict = Field(
        default_factory=dict,
        description="Raw triage result from alert triage module",
    )
    rca_confidence: float = Field(
        default=0.0,
        description="RCA confidence score (0.0-1.0)",
    )
    deployment_related: bool = Field(
        default=False,
        description="Whether a recent deployment triggered this",
    )
    pipeline_duration_seconds: float = Field(
        default=0.0,
        description="Total time the pipeline took to run",
    )


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------

class AIOpsPipeline:
    """
    Full AIops pipeline that chains all optimization modules.

    The pipeline is designed to be autonomous: given raw logs and metrics,
    it produces a complete incident report with root cause and runbook
    without human intervention.
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.client = LLMClient()
        self.rca_agent = RCAAgent(verbose=verbose)
        self.anomaly_detector = AnomalyDetector()

    def _log(self, message: str) -> None:
        if self.verbose:
            console.print(message)

    def run(self, logs: list[str], metrics: dict) -> IncidentReport:
        """
        Run the full AIops pipeline.

        Pipeline stages:
        1. Detect anomalies from metrics
        2. Triage the incident as an alert
        3. Run RCA if severity warrants it
        4. Generate runbook for the root cause
        5. Compile incident report

        Args:
            logs: List of log line strings
            metrics: Dict of metric_name -> list of values (time series)

        Returns:
            IncidentReport with complete incident analysis
        """
        pipeline_start = time.time()
        incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
        timestamp = datetime.now().isoformat()

        self._log(f"\n[bold yellow]Pipeline started: {incident_id}[/bold yellow]")

        # ===================================================================
        # Stage 1: Anomaly Detection
        # ===================================================================
        self._log("\n[bold cyan]Stage 1/5: Anomaly Detection[/bold cyan]")

        anomalies = detect_anomalies(metrics)
        self._log(f"  Found {len(anomalies)} anomalies")

        # Also run the multi-turn detector on the latest snapshot
        if metrics.get("timestamps"):
            latest_snapshot = {
                k: v[-1] if isinstance(v, list) else v
                for k, v in metrics.items()
            }
            anomaly_report = self.anomaly_detector.analyze(latest_snapshot)
            self._log(f"  Severity: {anomaly_report.severity}, Trend: {anomaly_report.trend}")
            # Merge anomalies
            anomalies.extend(anomaly_report.anomalies)
            # Deduplicate
            anomalies = list(dict.fromkeys(anomalies))

        if not anomalies:
            self._log("  [green]No anomalies detected. Pipeline complete.[/green]")
            return IncidentReport(
                incident_id=incident_id,
                severity="P4",
                timestamp=timestamp,
                anomalies=[],
                root_cause="No anomalies detected",
                affected_services=[],
                runbook_steps=[],
                resolution_time_estimate="N/A",
                actions_taken=["Anomaly scan completed - all clear"],
                pipeline_duration_seconds=time.time() - pipeline_start,
            )

        # ===================================================================
        # Stage 2: Alert Triage
        # ===================================================================
        self._log("\n[bold cyan]Stage 2/5: Alert Triage[/bold cyan]")

        # Build alert description from anomalies and metrics
        error_rate = metrics.get("error_rate", [0])[-1] if metrics.get("error_rate") else 0
        latency = metrics.get("latency_p99", [0])[-1] if metrics.get("latency_p99") else 0
        alert_text = (
            f"Production incident detected.\n"
            f"Error rate: {error_rate}%\n"
            f"P99 latency: {latency}ms\n"
            f"Anomalies: {'; '.join(anomalies[:5])}\n"
            f"Log samples: {logs[-3] if len(logs) >= 3 else logs[-1] if logs else 'N/A'}"
        )

        triage: AlertTriage = triage_alert(alert_text)
        self._log(f"  Severity: [bold]{triage.severity}[/bold] | Category: {triage.category}")
        self._log(f"  Escalate: {'YES' if triage.escalate_to_human else 'No'}")

        # ===================================================================
        # Stage 3: RCA (only for P1/P2)
        # ===================================================================
        rca_result: RCAResult | None = None

        if triage.severity in ("P1", "P2"):
            self._log("\n[bold cyan]Stage 3/5: Root Cause Analysis[/bold cyan]")

            # Build incident description from logs + metrics
            recent_errors = [l for l in logs if "ERROR" in l][-5:]
            incident_desc = (
                f"Severity: {triage.severity} incident.\n"
                f"Alert: {triage.summary}\n"
                f"Error rate: {error_rate}%, P99 latency: {latency}ms\n"
                f"Recent error logs:\n" + "\n".join(recent_errors)
            )

            try:
                rca_result = self.rca_agent.investigate(incident_desc)
                self._log(f"  Root cause: {rca_result.root_cause[:100]}...")
                self._log(f"  Confidence: {rca_result.confidence_score:.0%}")
            except Exception as e:
                self._log(f"  [red]RCA error: {e}[/red]")
        else:
            self._log(f"\n[dim]Stage 3/5: RCA skipped for {triage.severity}[/dim]")

        # ===================================================================
        # Stage 4: Runbook Generation
        # ===================================================================
        self._log("\n[bold cyan]Stage 4/5: Runbook Generation[/bold cyan]")

        incident_type = (
            rca_result.root_cause[:80] if rca_result
            else triage.summary[:80]
        )
        context = f"Services: {', '.join(rca_result.affected_services if rca_result else [triage.affected_component])}"

        try:
            runbook_data = generate_runbook(incident_type, context)
            runbook_text = runbook_data["runbook"]
            self._log(f"  Generated {len(runbook_text)} char runbook ({'cached' if runbook_data['from_cache'] else 'fresh'})")

            # Extract key steps (first 8 numbered items)
            runbook_steps = []
            for line in runbook_text.split("\n"):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith("-") or line.startswith("*")):
                    step = line.lstrip("0123456789.-* ").strip()
                    if len(step) > 10:
                        runbook_steps.append(step)
                        if len(runbook_steps) >= 8:
                            break
        except Exception as e:
            self._log(f"  [red]Runbook error: {e}[/red]")
            runbook_steps = ["Manual runbook creation required"]

        # ===================================================================
        # Stage 5: Compile Incident Report
        # ===================================================================
        self._log("\n[bold cyan]Stage 5/5: Compiling Incident Report[/bold cyan]")

        actions_taken = [
            f"Pipeline triggered at {timestamp}",
            f"Anomaly detection: {len(anomalies)} anomalies found",
            f"Alert triaged as {triage.severity}: {triage.suggested_action}",
        ]
        if rca_result:
            actions_taken.append(f"RCA completed with {rca_result.confidence_score:.0%} confidence")
        if triage.escalate_to_human:
            actions_taken.append("On-call engineer notified (simulated)")
        actions_taken.append("Runbook generated and linked to incident")

        pipeline_duration = time.time() - pipeline_start
        self._log(f"\n  [green]Pipeline complete in {pipeline_duration:.1f}s[/green]")

        return IncidentReport(
            incident_id=incident_id,
            severity=triage.severity,
            timestamp=timestamp,
            anomalies=anomalies,
            root_cause=rca_result.root_cause if rca_result else triage.summary,
            affected_services=rca_result.affected_services if rca_result else [triage.affected_component],
            runbook_steps=runbook_steps,
            resolution_time_estimate=f"{triage.estimated_resolution_minutes} minutes",
            actions_taken=actions_taken,
            triage_result=triage.model_dump(),
            rca_confidence=rca_result.confidence_score if rca_result else 0.0,
            deployment_related=rca_result.deployment_related if rca_result else False,
            pipeline_duration_seconds=pipeline_duration,
        )
