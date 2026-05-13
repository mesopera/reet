"""
Builds prompts for the LLM reasoning engine.
"""
import json
import platform
import socket
from datetime import datetime
from anomaly.anomaly_aggregator import AnomalyReport


SYSTEM_PROMPT = """You are an autonomous server fault diagnosis system.

Your job is to analyze flagged telemetry anomalies from a bare-metal Linux server and produce a structured incident report.

RULES:
- Never infer hardware fault without direct sensor evidence (SMART, IPMI, or ECC data)
- hardware_involved must be true ONLY if SMART, IPMI, or ECC signals are in the flagged list
- auto_remediable must be false if hardware_involved is true
- confidence must reflect genuine uncertainty — do not always output 0.99
- suggested_action must be exactly one of: restart_service, vacuum_logs, reap_zombies, trigger_vacuum, or null
- If auto_remediable is false, suggested_action must be null

OUTPUT FORMAT:
Respond with ONLY valid JSON. No markdown. No explanation. No preamble.
The JSON must match this exact schema:

{
  "root_cause": "string — one sentence describing the root cause",
  "root_cause_component": "string — the specific component e.g. sda, memory, nginx.service",
  "confidence": float between 0.0 and 1.0,
  "fault_category": "one of: hardware, os, application, network, database",
  "hardware_involved": boolean,
  "causal_chain": [
    {
      "timestamp_offset_seconds": float,
      "component": "string",
      "event": "string",
      "caused_by": "string or null"
    }
  ],
  "auto_remediable": boolean,
  "suggested_action": "one of: restart_service, vacuum_logs, reap_zombies, trigger_vacuum, or null",
  "plain_language_summary": "string — 2-3 sentences for a non-technical operator",
  "reasoning": "string — your internal reasoning chain, 3-5 sentences"
}"""


def build_system_prompt() -> str:
    return SYSTEM_PROMPT


def build_user_message(anomaly_report: AnomalyReport, system_context: dict = None) -> str:
    if system_context is None:
        system_context = _get_system_context()

    signals = []
    for sig in anomaly_report.flagged_signals:
        signals.append({
            "source": sig.source,
            "component": sig.component,
            "metric": sig.metric,
            "value": sig.value,
            "anomaly_type": sig.anomaly_type,
            "severity": round(sig.severity, 3),
            "details": sig.details
        })

    message = f"""SERVER CONTEXT:
{json.dumps(system_context, indent=2)}

FLAGGED ANOMALIES (detected at {anomaly_report.timestamp.isoformat()}):
{json.dumps(signals, indent=2)}

Total readings scanned this cycle: {anomaly_report.total_readings_scanned}

Analyze these anomalies and produce the incident report JSON."""

    return message


def _get_system_context() -> dict:
    try:
        hostname = socket.gethostname()
    except:
        hostname = "unknown"

    return {
        "hostname": hostname,
        "os": "Linux Ubuntu 22.04",
        "timestamp": datetime.utcnow().isoformat(),
        "mode": "simulate"
    }