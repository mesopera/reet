"""
Master control loop.
collect -> detect -> reason -> gate -> act or escalate
"""
import os
import time
import signal
import uuid
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from collector.orchestrator import TelemetryOrchestrator
from storage.influx_client import InfluxClient
from storage.incident_store import IncidentStore
from anomaly.anomaly_aggregator import AnomalyAggregator
from reasoning.correlator import Correlator
from remediation.gate_checker import GateChecker, ActionDecision, EscalationDecision
from remediation.executor import Executor
from remediation.audit_logger import AuditLogger

POLL_INTERVAL = int(os.getenv('POLL_INTERVAL_SECONDS', '60'))
CONFIDENCE_THRESHOLD = float(os.getenv('LLM_CONFIDENCE_THRESHOLD', '0.75'))

running = True


def handle_shutdown(signum, frame):
    global running
    print("\nShutdown signal received — finishing current cycle...")
    running = False


signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)


def startup_checks():
    print("=" * 50)
    print("Autonomous Server Healing System")
    print(f"Mode: {os.getenv('MODE', 'simulate')}")
    print(f"Poll interval: {POLL_INTERVAL}s")
    print(f"Confidence threshold: {CONFIDENCE_THRESHOLD}")
    print("=" * 50)

    # Check InfluxDB
    try:
        client = InfluxClient()
        client.close()
        print("[OK] InfluxDB reachable")
    except Exception as e:
        print(f"[WARN] InfluxDB not reachable: {e}")

    # Check SQLite
    try:
        store = IncidentStore()
        print("[OK] SQLite ready")
    except Exception as e:
        print(f"[FAIL] SQLite error: {e}")
        raise

    # Check API key
    api_key = os.getenv('GROQ_API_KEY')
    if api_key:
        print("[OK] Groq API key set")
    else:
        print("[WARN] Groq API key not set")

    print("=" * 50)


def run():
    startup_checks()

    orchestrator = TelemetryOrchestrator()
    influx = InfluxClient()
    store = IncidentStore()
    aggregator = AnomalyAggregator()
    correlator = Correlator()
    gate_checker = GateChecker(confidence_threshold=CONFIDENCE_THRESHOLD)
    executor = Executor()
    audit = AuditLogger()

    cycle = 0

    while running:
        cycle += 1
        print(f"\n[Cycle {cycle}] {datetime.utcnow().isoformat()}")

        # Step 1: Collect
        try:
            snapshot = orchestrator.collect()
        except Exception as e:
            print(f"  [ERROR] Collection failed: {e}")
            time.sleep(POLL_INTERVAL)
            continue

        # Step 2: Write to InfluxDB
        try:
            influx.write(snapshot.readings)
        except Exception as e:
            print(f"  [WARN] InfluxDB write failed: {e}")

        # Step 3: Anomaly detection
        report = aggregator.run(snapshot)

        if not report.flagged_signals:
            print(f"  No anomalies detected ({report.total_readings_scanned} readings scanned)")
            time.sleep(POLL_INTERVAL)
            continue

        print(f"  [!] {len(report.flagged_signals)} anomalies flagged:")
        for sig in report.flagged_signals:
            print(f"      {sig.source}/{sig.component}/{sig.metric} — {sig.anomaly_type} (severity={sig.severity:.2f})")

        # Step 4: LLM reasoning
        print("  Calling LLM for root cause analysis...")
        incident = correlator.correlate(report)

        if incident is None:
            print("  [WARN] LLM reasoning failed — escalating raw anomaly report")
            audit.log_escalation(
                None,
                'llm_failed',
                f"Raw anomalies: {[s.metric for s in report.flagged_signals]}"
            )
            time.sleep(POLL_INTERVAL)
            continue

        incident_id = str(uuid.uuid4())
        print(f"  Root cause: {incident.root_cause}")
        print(f"  Confidence: {incident.confidence}")
        print(f"  Category: {incident.fault_category}")
        print(f"  Hardware involved: {incident.hardware_involved}")

        # Step 5: Gate check
        decision = gate_checker.evaluate(incident, incident_id)

        if isinstance(decision, ActionDecision):
            print(f"  [->] All gates passed — executing: {decision.action_id}")
            result = executor.execute(decision)
            if result.success:
                print(f"  [OK] Action completed successfully")
            else:
                print(f"  [FAIL] Action failed: {result.output}")

        elif isinstance(decision, EscalationDecision):
            print(f"  [^] Escalating to human — gate failed: {decision.gate_failed}")
            print(f"  Reason: {decision.reason}")

            human_report = (
                f"INCIDENT REPORT\n"
                f"Root Cause: {incident.root_cause}\n"
                f"Component: {incident.root_cause_component}\n"
                f"Confidence: {incident.confidence}\n"
                f"Category: {incident.fault_category}\n"
                f"Hardware Involved: {incident.hardware_involved}\n\n"
                f"Summary: {incident.plain_language_summary}\n\n"
                f"Causal Chain:\n" +
                "\n".join([f"  - {s.component}: {s.event}" for s in incident.causal_chain])
            )

            audit.log_escalation(incident_id, decision.reason, human_report)
            print(f"  Human report saved to audit log")

        time.sleep(POLL_INTERVAL)

    print("Pipeline shut down cleanly.")
    influx.close()


if __name__ == '__main__':
    run()