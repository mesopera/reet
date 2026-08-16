"""
Demo driver — natural, randomized rotation through real and simulated faults.
Order and durations reshuffle every loop so back-to-back runs never look identical.
Hardware faults are capped and rare, matching realistic proportions.
Compound faults fire multiple real signals at once so the LLM has correlated
events to reason across instead of a single isolated spike.
"""
import os, uuid, time, random
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
os.environ["MODE"] = "simulate"

from simulator.smart_simulator import SmartSimulator
from simulator.ecc_simulator import EccSimulator
from simulator.ipmi_simulator import IpmiSimulator
from collector.hardware.smart_collector import SmartCollector
from collector.hardware.ipmi_collector import IpmiCollector
from collector.hardware.ecc_collector import EccCollector
from collector.os_layer.proc_collector import ProcCollector
from collector.os_layer.disk_collector import DiskCollector
from collector.services.process_collector import ProcessCollector
from collector.orchestrator import CollectionSnapshot
from anomaly.anomaly_aggregator import AnomalyAggregator
from reasoning.correlator import Correlator
from remediation.gate_checker import GateChecker, ActionDecision, EscalationDecision
from remediation.executor import Executor
from remediation.audit_logger import AuditLogger
from fault_injection.scenarios.zombie_factory import ZombieFactoryScenario
from fault_injection.scenarios.disk_fill import DiskFillScenario
from fault_injection.scenarios.log_flood import LogFloodScenario
from fault_injection.scenarios.db_vacuum_starve import DbVacuumStarveScenario
from fault_injection.scenarios.nfs_hang_sim import NfsHangScenario
from fault_injection.scenarios.cpu_stress import CpuStressScenario
from fault_injection.scenarios.memory_pressure import MemoryPressureScenario

POLL = int(os.getenv("POLL_INTERVAL_SECONDS", "3"))

agg   = AnomalyAggregator()
corr  = Correlator()
gate  = GateChecker()
exec_ = Executor()
audit = AuditLogger()
cycle_num = 0


def reset_hw_history():
    """Clear SMART/ECC long-window history so one phase's fault trajectory
    never bleeds into the next, in either direction."""
    agg.smart_accel.history.clear()
    agg.ecc_rate.history = []


def run_cycle(collectors, phase_name):
    global cycle_num
    cycle_num += 1
    ts = datetime.utcnow()
    print(f"\n[Cycle {cycle_num}] {ts.isoformat()}  phase={phase_name}")

    readings = []
    for col in collectors:
        r = col.collect()
        for x in r:
            x.timestamp = ts
        readings.extend(r)
    print(f"  Collected {len(readings)} readings from {len(collectors)} sources")

    snap = CollectionSnapshot(str(uuid.uuid4()), ts, readings, {})
    report = agg.run(snap)

    if not report.flagged_signals:
        print(f"  No anomalies detected ({report.total_readings_scanned} readings scanned)")
        return False

    print(f"  [!] {len(report.flagged_signals)} anomalies flagged:")
    for sig in report.flagged_signals:
        print(f"      {sig.source}/{sig.component}/{sig.metric} — {sig.anomaly_type} (severity={sig.severity:.2f})")

    print("  Calling LLM for root cause analysis...")
    result = corr.correlate(report)
    if result is None:
        print("  [WARN] LLM reasoning failed — escalating raw anomaly report")
        audit.log_escalation(None, 'llm_failed', f"Raw anomalies: {[s.metric for s in report.flagged_signals]}")
        return True

    incident, incident_id = result
    print(f"  Root cause: {incident.root_cause}")
    print(f"  Confidence: {incident.confidence}")
    print(f"  Category: {incident.fault_category}")
    print(f"  Hardware involved: {incident.hardware_involved}")

    decision = gate.evaluate(incident, incident_id)
    if isinstance(decision, ActionDecision):
        print(f"  [->] All gates passed — executing: {decision.action_id}")
        result = exec_.execute(decision)
        print(f"  [OK] Action completed successfully" if result.success else f"  [FAIL] {result.output}")
    elif isinstance(decision, EscalationDecision):
        print(f"  [^] Escalating to human — gate failed: {decision.gate_failed}")
        print(f"  Reason: {decision.reason}")
        if incident.hardware_involved:
            from hardware_diagnostics.report_generator import generate as gen_hw
            hw_sig = next((s for s in report.flagged_signals if s.source in ('smart','ecc','ipmi')), report.flagged_signals[0])
            human_report = gen_hw(incident, hw_sig)
        else:
            human_report = incident.plain_language_summary
        audit.log_escalation(incident_id, decision.reason, human_report)
        print("  Human report saved to audit log")
    return True


def make_collectors(smart_profile="healthy_baseline", ecc_profile="healthy_baseline"):
    return [
        SmartCollector(simulator=SmartSimulator(smart_profile)),
        IpmiCollector(simulator=IpmiSimulator("healthy_baseline")),
        EccCollector(simulator=EccSimulator(ecc_profile)),
        ProcCollector(),
        DiskCollector(),
        ProcessCollector(),
    ]


def idle_gap():
    """A short, randomized natural pause between phases — real systems don't
    snap instantly from one state to the next."""
    gap = random.uniform(2, 5)
    print(f"\n  -- system idle, monitoring continues ({gap:.1f}s) --")
    time.sleep(gap)


def run_healthy(min_s=10, max_s=20):
    dur = random.randint(min_s, max_s)
    print(f"\n{'='*70}\nPHASE: Healthy baseline  ({dur}s)\n{'='*70}")
    collectors = make_collectors()
    end = time.time() + dur
    while time.time() < end:
        run_cycle(collectors, "Healthy baseline")
        time.sleep(POLL)


def run_real_fault(name, scenario_factory, min_s=15, max_s=25, max_incidents=2):
    dur = random.randint(min_s, max_s)
    print(f"\n{'='*70}\nPHASE: {name}  (real fault_injection, {dur}s)\n{'='*70}")
    scenario = scenario_factory()
    collectors = make_collectors()
    print("  injecting real fault via fault_injection scenario...")
    scenario.inject()
    time.sleep(2)
    print(f"  verified injected: {scenario.verify_injected()}")
    incidents = 0
    end = time.time() + dur
    while time.time() < end:
        fired = run_cycle(collectors, name)
        if fired:
            incidents += 1
            if incidents >= max_incidents:
                print(f"  (reached {max_incidents} incidents — moving on)")
                break
        time.sleep(POLL)
    scenario.cleanup()
    print("  cleaned up")


def run_hardware_fault(name, smart_profile="healthy_baseline", ecc_profile="healthy_baseline",
                        min_s=15, max_s=25, max_incidents=1):
    dur = random.randint(min_s, max_s)
    print(f"\n{'='*70}\nPHASE: {name}  ({dur}s)\n{'='*70}")
    reset_hw_history()
    collectors = make_collectors(smart_profile, ecc_profile)
    incidents = 0
    end = time.time() + dur
    while time.time() < end:
        fired = run_cycle(collectors, name)
        if fired:
            incidents += 1
            if incidents >= max_incidents:
                print(f"  (reached {max_incidents} incidents — moving on)")
                break
        time.sleep(POLL)
    reset_hw_history()  # symmetric — never let this leak into whatever comes next


def run_compound_fault(name, scenario_factories, min_s=20, max_s=30, max_incidents=2):
    """A compound fault — fires TWO (or more) real scenarios at once so the LLM
    sees multiple correlated signals and can build a real multi-step causal chain."""
    dur = random.randint(min_s, max_s)
    print(f"\n{'='*70}\nPHASE: {name}  (compound, {dur}s)\n{'='*70}")
    scenarios = [f() for f in scenario_factories]
    collectors = make_collectors()
    for sc in scenarios:
        print(f"  injecting: {sc.__class__.__name__}")
        sc.inject()
    time.sleep(2)
    incidents = 0
    end = time.time() + dur
    while time.time() < end:
        fired = run_cycle(collectors, name)
        if fired:
            incidents += 1
            if incidents >= max_incidents:
                print(f"  (reached {max_incidents} incidents — moving on)")
                break
        time.sleep(POLL)
    for sc in scenarios:
        sc.cleanup()
    print("  cleaned up")


# ── Scenario pool — 5 real software faults, 2 rare hardware faults, 2 compound faults ──
SOFTWARE_FAULTS = [
    ("Zombie processes (auto-fix expected)", lambda: ZombieFactoryScenario(count=15)),
    ("Disk filling (auto-fix expected)", lambda: DiskFillScenario(target_percent=0.75)),
    ("Log flood (auto-fix expected)", lambda: LogFloodScenario(messages_per_second=60, duration_seconds=20)),
    ("Database bloat (auto-fix expected)", lambda: DbVacuumStarveScenario()),
    ("NFS hang (escalation expected)", lambda: NfsHangScenario(duration_seconds=20)),
]

HARDWARE_FAULTS = [
    ("Disk degrading (hardware escalation)", dict(smart_profile="disk_failing_slow")),
    ("Memory degrading (hardware escalation)", dict(ecc_profile="memory_degrading")),
]

COMPOUND_FAULTS = [
    ("CPU + Memory pressure (compound, escalation likely)",
     [lambda: CpuStressScenario(cores=2, duration_seconds=25),
      lambda: MemoryPressureScenario(percent_of_ram=0.7, duration_seconds=25)]),
    ("Disk fill + Zombie storm (compound, multi-symptom)",
     [lambda: DiskFillScenario(target_percent=0.8),
      lambda: ZombieFactoryScenario(count=25)]),
]


if __name__ == "__main__":
    print("DEMO DRIVER — randomized rotation, quick succession, loops forever")
    print("Ctrl+C to stop\n")
    try:
        loop_n = 0
        while True:
            loop_n += 1
            # Build this loop's running order fresh — every pass looks different.
            # 5 software faults every loop, but only ONE hardware fault every
            # OTHER loop — hardware stays the rare, notable event it should be.
            # Compound faults alternate with hardware faults so both stay rare
            # and distinct events rather than piling up in the same loop.
            order = list(SOFTWARE_FAULTS)
            random.shuffle(order)
            if loop_n % 2 == 1:
                hw_name, hw_kwargs = random.choice(HARDWARE_FAULTS)
                insert_at = random.randint(1, len(order) - 1)
                order.insert(insert_at, (hw_name, hw_kwargs))
            if loop_n % 2 == 0:
                name, factories = random.choice(COMPOUND_FAULTS)
                insert_at = random.randint(1, len(order))
                order.insert(insert_at, (name, factories))

            for name, spec in order:
                run_healthy()
                idle_gap()
                if isinstance(spec, list):
                    run_compound_fault(name, spec)
                elif isinstance(spec, dict):
                    run_hardware_fault(name, **spec)
                else:
                    run_real_fault(name, spec)
                idle_gap()

    except KeyboardInterrupt:
        print("\nDemo driver stopped.")