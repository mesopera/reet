# Autonomous Server Healing System — Complete Project Scaffold

## Environment
- GitHub Codespaces (8-core, 16GB RAM)
- Python 3.11
- Claude API (Anthropic) for LLM reasoning
- Simulated hardware telemetry + real /proc, /sys, journald

---

## Repository Structure

```
autonomous-server-healing/
│
├── .devcontainer/
│   └── devcontainer.json          # Codespaces environment config
│
├── .github/
│   └── workflows/
│       └── test.yml               # CI — runs test suite on push
│
├── config/
│   ├── settings.yaml              # Global thresholds, model config, paths
│   ├── whitelist.yaml             # Approved auto-remediation actions
│   └── vendor_smart_tables.json   # Vendor-specific SMART attribute maps
│
├── simulator/
│   ├── __init__.py
│   ├── smart_simulator.py         # Generates SMART telemetry streams
│   ├── ipmi_simulator.py          # Generates IPMI sensor readings
│   ├── ecc_simulator.py           # Generates ECC/MCE error streams
│   ├── fault_profiles/
│   │   ├── disk_failing.yaml      # SMART degradation fault profile
│   │   ├── memory_degrading.yaml  # ECC acceleration fault profile
│   │   ├── cpu_thermal.yaml       # CPU temp escalation profile
│   │   ├── psu_unstable.yaml      # PSU voltage ripple profile
│   │   └── healthy_baseline.yaml  # Normal operation baseline
│   └── backblaze_loader.py        # Loads real Backblaze dataset for calibration
│
├── collector/
│   ├── __init__.py
│   ├── base_collector.py          # Abstract base class for all collectors
│   ├── hardware/
│   │   ├── __init__.py
│   │   ├── smart_collector.py     # Reads from simulator or real smartctl
│   │   ├── ipmi_collector.py      # Reads from simulator or real ipmitool
│   │   └── ecc_collector.py       # Reads from simulator or real rasdaemon
│   ├── os_layer/
│   │   ├── __init__.py
│   │   ├── proc_collector.py      # /proc/meminfo, /proc/stat, /proc/loadavg
│   │   ├── sys_collector.py       # /sys/block/*/stat, /sys/class/net/*
│   │   └── disk_collector.py      # df, inode usage
│   ├── services/
│   │   ├── __init__.py
│   │   ├── journald_collector.py  # systemd journal reader
│   │   └── process_collector.py   # /proc/<pid> per-process stats
│   ├── database/
│   │   ├── __init__.py
│   │   └── postgres_collector.py  # pg_stat_activity, pg_stat_bgwriter
│   └── orchestrator.py            # Runs all collectors in parallel, timestamps output
│
├── storage/
│   ├── __init__.py
│   ├── influx_client.py           # InfluxDB write/query wrapper
│   ├── incident_store.py          # SQLite incident record CRUD
│   └── schema.sql                 # SQLite schema definition
│
├── anomaly/
│   ├── __init__.py
│   ├── zscore_detector.py         # Univariate Z-score spike detection
│   ├── isolation_forest.py        # Multivariate Isolation Forest
│   ├── seasonal_baseline.py       # statsmodels seasonal decomposition
│   ├── smart_acceleration.py      # First/second derivative on SMART attributes
│   ├── ecc_rate_model.py          # Sliding window ECC rate-of-change
│   └── anomaly_aggregator.py      # Combines all detectors, returns flagged signals
│
├── reasoning/
│   ├── __init__.py
│   ├── llm_client.py              # Claude API wrapper (swap target for Ollama)
│   ├── prompt_builder.py          # Builds structured JSON context window for LLM
│   ├── response_parser.py         # Parses + validates LLM JSON output via pydantic
│   ├── schemas.py                 # Pydantic models: IncidentReport, CausalChain, etc.
│   └── correlator.py              # Orchestrates: anomalies → prompt → LLM → incident
│
├── remediation/
│   ├── __init__.py
│   ├── gate_checker.py            # Confidence gate, whitelist gate, hardware gate
│   ├── executor.py                # Runs whitelisted actions via subprocess
│   ├── snapshot.py                # Pre-action rsync state snapshot
│   ├── audit_logger.py            # Append-only SQLite audit trail writer
│   └── actions/
│       ├── __init__.py
│       ├── restart_service.py     # systemctl restart <unit>
│       ├── vacuum_logs.py         # journalctl --vacuum-size / log rotation
│       ├── remount_nfs.py         # Detect and remount hung NFS
│       ├── reap_zombies.py        # Kill zombie processes
│       └── trigger_vacuum.py      # PostgreSQL VACUUM ANALYZE
│
├── hardware_diagnostics/
│   ├── __init__.py
│   ├── component_localizer.py     # Maps fault to specific slot/bay/port
│   ├── urgency_model.py           # scipy curve fitting on error acceleration
│   ├── vendor_lookup.py           # Vendor SMART table + part number lookup
│   └── report_generator.py        # LLM-generated plain-language repair report
│
├── fault_injection/
│   ├── __init__.py
│   ├── injector.py                # Orchestrates injection scenarios
│   ├── scenarios/
│   │   ├── disk_fill.py           # fallocate to X% disk usage
│   │   ├── memory_pressure.py     # stress-ng memory hog
│   │   ├── cpu_stress.py          # stress-ng CPU load
│   │   ├── zombie_factory.py      # Spawns zombie processes
│   │   ├── nfs_hang_sim.py        # Simulates NFS mount hang
│   │   ├── log_flood.py           # Floods journald with log writes
│   │   └── db_vacuum_starve.py    # Blocks PostgreSQL autovacuum
│   └── scenario_runner.py         # Runs scenario × 5 reps, records MTTD/MTTR
│
├── evaluation/
│   ├── __init__.py
│   ├── metrics_recorder.py        # Records MTTD, MTTR, TP, FP, FN per scenario
│   ├── baseline_runner.py         # Runs same scenarios with no automation
│   ├── wilcoxon_test.py           # scipy.stats Wilcoxon signed-rank test
│   └── results_plotter.py         # matplotlib/seaborn result charts
│
├── pipeline/
│   ├── __init__.py
│   └── main_loop.py               # Master loop: collect → detect → reason → act
│
├── tests/
│   ├── unit/
│   │   ├── test_smart_simulator.py
│   │   ├── test_anomaly_detectors.py
│   │   ├── test_prompt_builder.py
│   │   ├── test_response_parser.py
│   │   ├── test_gate_checker.py
│   │   ├── test_executor.py
│   │   └── test_audit_logger.py
│   ├── integration/
│   │   ├── test_collect_to_anomaly.py
│   │   ├── test_anomaly_to_llm.py
│   │   └── test_llm_to_remediation.py
│   └── e2e/
│       └── test_full_pipeline.py  # Inject fault → verify detection + remediation
│
├── notebooks/
│   ├── 01_backblaze_exploration.ipynb
│   ├── 02_smart_acceleration_model.ipynb
│   ├── 03_isolation_forest_tuning.ipynb
│   └── 04_results_analysis.ipynb
│
├── data/
│   ├── backblaze/                 # Downloaded Backblaze CSVs (gitignored)
│   ├── snapshots/                 # Pre-action state snapshots (gitignored)
│   └── results/                   # Experiment result CSVs
│
├── docs/
│   ├── architecture.md
│   ├── fault_taxonomy.md
│   └── prompt_design.md
│
├── .env.example                   # ANTHROPIC_API_KEY=your_key_here
├── .gitignore
├── requirements.txt
├── setup.py
└── README.md
```

---

## Step 0 — Repository and Codespaces Setup

### 0.1 Create the repo
```bash
# On GitHub: New repository → autonomous-server-healing → Python .gitignore → MIT license
# Then open in Codespaces: Code → Codespaces → New codespace
# Request: 8-core 16GB machine type
```

### 0.2 devcontainer.json
```json
{
  "name": "autonomous-server-healing",
  "image": "mcr.microsoft.com/devcontainers/python:3.11",
  "features": {
    "ghcr.io/devcontainers/features/node:1": {}
  },
  "postCreateCommand": "pip install -r requirements.txt && cp .env.example .env",
  "customizations": {
    "vscode": {
      "extensions": [
        "ms-python.python",
        "ms-python.black-formatter",
        "ms-toolsai.jupyter",
        "eamodio.gitlens"
      ]
    }
  },
  "forwardPorts": [8086, 8888]
}
```

### 0.3 requirements.txt
```
# LLM
anthropic>=0.30.0

# Data
pandas>=2.0.0
numpy>=1.26.0
scipy>=1.11.0
scikit-learn>=1.3.0
statsmodels>=0.14.0

# Storage
influxdb-client>=1.38.0
SQLAlchemy>=2.0.0

# Validation
pydantic>=2.0.0
pyyaml>=6.0

# Database connectors
psycopg2-binary>=2.9.0

# Visualization (evaluation only)
matplotlib>=3.7.0
seaborn>=0.12.0

# Testing
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-asyncio>=0.21.0

# Dev
black>=23.0.0
python-dotenv>=1.0.0
```

### 0.4 Install InfluxDB in Codespaces
```bash
# Run once after Codespace starts
wget https://dl.influxdata.com/influxdb/releases/influxdb2-2.7.1_linux_amd64.tar.gz
tar xzf influxdb2-2.7.1_linux_amd64.tar.gz
sudo cp influxdb2-2.7.1/usr/bin/influxd /usr/local/bin/

# Start it (background)
influxd &

# Setup (one time)
influx setup \
  --username admin \
  --password adminpassword \
  --org healing-system \
  --bucket telemetry \
  --force
```

### 0.5 .env file
```
ANTHROPIC_API_KEY=sk-ant-your-key-here
INFLUX_URL=http://localhost:8086
INFLUX_TOKEN=your-influx-token
INFLUX_ORG=healing-system
INFLUX_BUCKET=telemetry
SQLITE_PATH=data/incidents.db
SNAPSHOT_DIR=data/snapshots
MODE=simulate         # 'simulate' or 'live'
LLM_CONFIDENCE_THRESHOLD=0.75
```

---

## Step 1 — Build the Simulator

**Goal:** Produce realistic SMART, IPMI, and ECC data streams that a real collector would produce. The rest of the system never needs to know whether data is real or simulated.

### 1.1 Download Backblaze Dataset (calibration data)
```bash
# Free public dataset — real SMART readings from 200,000+ drives, including failed ones
# Download Q4 2023 from: https://www.backblaze.com/cloud-storage/resources/hard-drive-test-data
# Place CSVs in data/backblaze/
# File: 2023-Q4/
```

### 1.2 simulator/smart_simulator.py
```python
"""
Generates realistic SMART telemetry streams.
Calibrated against Backblaze failure signatures.

Fault modes:
  - 'healthy'         : stable attributes, no trend
  - 'reallocating'    : reallocated_sector_ct increasing (accelerating)
  - 'pending'         : pending_sector_count growing
  - 'wear_out'        : SSD wear_leveling_count approaching limit
  - 'seek_errors'     : seek_error_rate spiking

Each call to get_reading() returns a dict matching the real smartctl JSON schema.
"""
```

Key attributes to simulate (map to real SMART IDs):
- `ID#5`  — Reallocated Sector Count
- `ID#187` — Reported Uncorrectable Errors
- `ID#188` — Command Timeout
- `ID#197` — Current Pending Sector Count
- `ID#198` — Offline Uncorrectable

For 'reallocating' fault mode, the simulator increments attribute 5 using:
```
value(t) = baseline + A * e^(k*t) + noise
```
Where `A` and `k` are fit from real Backblaze pre-failure curves.

### 1.3 simulator/ipmi_simulator.py
Simulates output matching real `ipmitool sdr list` format:
```
CPU Temp        | 42 degrees C  | ok
Fan1            | 2400 RPM      | ok
Volt_12V        | 12.10 Volts   | ok
PS1 Status      | Presence detected | ok
```

Fault modes: `cpu_thermal` (temp escalates), `fan_fail` (RPM → 0), `psu_unstable` (voltage ripple).

### 1.4 simulator/ecc_simulator.py
Simulates `/sys/devices/system/edac/mc0/ce_count` (correctable errors).

Fault modes:
- `healthy` : ce_count stable at 0–2 per hour
- `degrading` : ce_count increasing, rate doubling every N hours

### 1.5 fault_profiles/*.yaml
Example `disk_failing.yaml`:
```yaml
name: disk_failing
duration_hours: 48
smart:
  fault_mode: reallocating
  start_value: 5
  acceleration_factor: 1.8    # doubles roughly every 8 hours
  noise_std: 0.5
ipmi:
  fault_mode: healthy           # disk failure doesn't affect IPMI
ecc:
  fault_mode: healthy
expected_detection_window_hours: 12   # how early system should catch it
expected_remediation: human_escalation  # hardware fault = always escalate
```

---

## Step 2 — Build the Collector

**Goal:** Single interface that returns a unified telemetry snapshot regardless of whether data comes from the simulator or a real system.

### 2.1 collector/base_collector.py
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

@dataclass
class TelemetryReading:
    source: str           # 'smart', 'ipmi', 'ecc', 'proc', etc.
    component: str        # 'sda', 'cpu0', 'dimm_a2', etc.
    metric: str           # 'reallocated_sector_ct', 'cpu_temp', etc.
    value: float
    unit: str
    timestamp: datetime
    raw: dict             # full original reading

class BaseCollector(ABC):
    @abstractmethod
    def collect(self) -> list[TelemetryReading]:
        """Return list of readings from this source."""
        pass
```

### 2.2 collector/orchestrator.py
```python
"""
Runs all collectors in parallel using ThreadPoolExecutor.
Timestamps every reading to a common reference clock.
Writes to InfluxDB.
Returns unified snapshot dict for anomaly detection.
"""
```

Key design: all collectors are called simultaneously, readings are tagged with a shared `run_id` timestamp. This is what enables cross-layer causal ordering later.

### 2.3 Mode switching
In each collector, check `MODE` env var:
```python
import os
MODE = os.getenv('MODE', 'simulate')

class SmartCollector(BaseCollector):
    def collect(self):
        if MODE == 'simulate':
            return self.simulator.get_reading()
        else:
            return self._run_smartctl()
```

This means the entire system can switch between simulated and real telemetry with one env var change.

---

## Step 3 — Build the Storage Layer

**Goal:** Time-series data into InfluxDB, incident records into SQLite.

### 3.1 storage/influx_client.py
```python
"""
Wrapper around influxdb-client.
Methods:
  write(readings: list[TelemetryReading]) -> None
  query_range(metric, component, start, end) -> pd.DataFrame
  query_latest(metric, component) -> TelemetryReading
"""
```

### 3.2 storage/schema.sql
```sql
CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY,
    detected_at TEXT NOT NULL,
    root_cause TEXT NOT NULL,
    confidence REAL NOT NULL,
    causal_chain TEXT NOT NULL,    -- JSON string
    fault_category TEXT NOT NULL,
    hardware_involved INTEGER NOT NULL,
    action_taken TEXT,             -- NULL if escalated
    action_outcome TEXT,
    escalated INTEGER NOT NULL,
    human_report TEXT,             -- plain-language report if escalated
    reasoning_chain TEXT NOT NULL, -- full LLM reasoning, always stored
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,      -- 'detection', 'gate_check', 'action', 'escalation'
    detail TEXT NOT NULL,
    FOREIGN KEY (incident_id) REFERENCES incidents(id)
);
```

---

## Step 4 — Build the Anomaly Detection Layer

**Goal:** Filter the continuous telemetry stream so only genuinely anomalous readings reach the LLM.

### 4.1 anomaly/zscore_detector.py
```python
"""
Maintains a rolling window (default 1 hour) of values per metric.
Flags any reading more than N standard deviations from rolling mean.
N is configurable per metric in settings.yaml (default: 3.0).
"""
```

### 4.2 anomaly/isolation_forest.py
```python
"""
Trained on the first N readings (warm-up period) to learn normal behavior.
Thereafter scores each new snapshot.
Anomaly score < -0.1 → flagged (sklearn convention).
Re-trains every 24 hours on recent data.
"""
```

### 4.3 anomaly/smart_acceleration.py
```python
"""
Core novel component.

For each SMART attribute:
1. Pull last 72 hours of readings from InfluxDB
2. Compute first derivative: delta_v / delta_t per interval
3. Compute second derivative: rate of change of rate
4. If second_derivative > threshold AND value > min_concern_threshold:
   → flag with urgency score = second_derivative * value

This catches a drive that had 10 bad sectors last week and 40 this week
even if 40 is below any absolute alarm threshold.
"""
```

### 4.4 anomaly/anomaly_aggregator.py
```python
"""
Runs all detectors.
Returns AnomalyReport:
  flagged_signals: list of FlaggedSignal
    - source, component, metric, value, anomaly_type, severity (0-1)
  timestamp: datetime
  run_id: str

Only passes to LLM if len(flagged_signals) > 0.
"""
```

---

## Step 5 — Build the LLM Reasoning Layer

**Goal:** Take flagged anomalies across all layers, produce a structured incident report with root cause, causal chain, and confidence score.

### 5.1 reasoning/schemas.py
```python
from pydantic import BaseModel, Field

class CausalStep(BaseModel):
    timestamp_offset_seconds: float
    component: str
    event: str
    caused_by: str | None

class IncidentReport(BaseModel):
    root_cause: str
    root_cause_component: str
    confidence: float = Field(ge=0.0, le=1.0)
    fault_category: str   # 'hardware', 'os', 'application', 'network', 'database'
    hardware_involved: bool
    causal_chain: list[CausalStep]
    auto_remediable: bool
    suggested_action: str | None
    plain_language_summary: str
    reasoning: str        # full chain of thought, stored in audit log
```

### 5.2 reasoning/prompt_builder.py
```python
"""
Builds the system prompt + user message sent to Claude.

System prompt establishes:
- Role: you are a server fault diagnosis system
- Output format: strict JSON matching IncidentReport schema
- Rules: never guess hardware faults without sensor evidence
- Schema: paste the full JSON schema

User message contains:
- Server context: OS, hostname, running services, uptime
- Flagged anomalies: list of FlaggedSignal objects as JSON
- Recent telemetry history summary: last 6 hours of relevant metrics
- Known system state: disk usage, memory usage, load average

Example flagged anomalies block:
{
  "flagged_signals": [
    {
      "source": "smart",
      "component": "sda",
      "metric": "reallocated_sector_ct",
      "value": 47,
      "anomaly_type": "acceleration",
      "severity": 0.82,
      "trend": "doubling every 9 hours"
    },
    {
      "source": "journald",
      "component": "postgresql",
      "metric": "log_errors",
      "value": 34,
      "anomaly_type": "spike",
      "severity": 0.61,
      "trend": "12x above baseline"
    }
  ]
}
"""
```

### 5.3 reasoning/llm_client.py
```python
"""
Thin wrapper around Anthropic client.
Sends prompt, receives response, extracts text content.
Handles retries on rate limit.
Designed so the call signature is identical to what Ollama would use —
swap the backend by changing one env var.
"""

import anthropic
import os

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def call_llm(system_prompt: str, user_message: str) -> str:
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=2000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}]
    )
    return response.content[0].text
```

### 5.4 reasoning/response_parser.py
```python
"""
Takes raw LLM text output.
Extracts JSON (handles markdown code blocks).
Validates against IncidentReport pydantic schema.
On validation failure: logs error, returns None → triggers escalation.
Never passes invalid output downstream.
"""
```

### 5.5 reasoning/correlator.py
```python
"""
Orchestrates the full reasoning step:
1. Receive AnomalyReport
2. Build prompt
3. Call LLM
4. Parse + validate response
5. Return IncidentReport or None (on parse failure)
6. Write to incident store
"""
```

---

## Step 6 — Build the Remediation Engine

**Goal:** Three safety gates then action, or structured human report.

### 6.1 config/whitelist.yaml
```yaml
actions:
  - id: restart_service
    description: "Restart a failed systemd service unit"
    requires:
      fault_category: application
      hardware_involved: false
    parameters:
      - name: unit_name
        type: string
        pattern: "^[a-z0-9_-]+\\.service$"   # strict regex, no injection
    command: "systemctl restart {unit_name}"
    sudo_required: true
    reversible: true

  - id: vacuum_logs
    description: "Truncate journal logs to free disk space"
    requires:
      fault_category: os
      hardware_involved: false
    parameters:
      - name: max_size
        type: string
        pattern: "^[0-9]+[MG]$"
    command: "journalctl --vacuum-size={max_size}"
    sudo_required: true
    reversible: false

  - id: reap_zombies
    description: "Kill zombie processes by signaling parent"
    requires:
      fault_category: os
      hardware_involved: false
    parameters: []
    command: "internal"           # handled in reap_zombies.py, not subprocess
    sudo_required: false
    reversible: true

  - id: trigger_vacuum
    description: "Run PostgreSQL VACUUM ANALYZE"
    requires:
      fault_category: database
      hardware_involved: false
    parameters:
      - name: table_name
        type: string
        pattern: "^[a-z_]+$"
    command: "internal"           # psycopg2 call, not subprocess
    sudo_required: false
    reversible: false
```

### 6.2 remediation/gate_checker.py
```python
"""
Three gates, evaluated in order. All must pass.

Gate 1 — Confidence Gate
  incident.confidence >= settings.LLM_CONFIDENCE_THRESHOLD (default 0.75)
  Fail → escalate with full report

Gate 2 — Whitelist Gate
  incident.suggested_action in whitelist.yaml
  AND all parameters match their regex patterns
  Fail → escalate

Gate 3 — Hardware Safety Gate
  incident.hardware_involved == False
  Fail → escalate (always, no exceptions)

All gates pass → return approved action
Any gate fails → return EscalationDecision with reason
"""
```

### 6.3 remediation/executor.py
```python
"""
Receives approved action from gate_checker.
1. Call snapshot.py to capture pre-action state
2. Write audit log entry: 'action_starting'
3. Execute action (subprocess or internal handler)
4. Monitor for 60 seconds: did the anomaly resolve?
5. Write audit log entry: 'action_complete' with outcome
6. Return ActionResult
"""
```

### 6.4 hardware_diagnostics/report_generator.py
```python
"""
Called when hardware_involved == True.
Builds a second LLM prompt with:
  - Full SMART data for the affected component
  - IPMI sensor data
  - ECC error history
  - Current workload context (what services are running)
  - Vendor SMART table for this drive model

LLM returns a plain-language report structured as:
  {
    "component": "Drive sda (WDC WD40EFRX-68N32N0)",
    "physical_location": "Drive bay 1",
    "urgency": "HIGH — failure likely within 48-72 hours",
    "what_is_happening": "...",
    "what_to_do": ["Step 1...", "Step 2...", ...],
    "data_risk": "...",
    "replacement_part": "WD Red Plus 4TB (WD40EFPX) or equivalent"
  }
"""
```

---

## Step 7 — Build the Pipeline

### 7.1 pipeline/main_loop.py
```python
"""
Master control loop. Runs indefinitely.

Every POLL_INTERVAL seconds (default: 60):
  1. orchestrator.collect()          → raw telemetry snapshot
  2. influx_client.write()           → persist to InfluxDB
  3. anomaly_aggregator.run()        → AnomalyReport
  4. if no anomalies: continue
  5. correlator.correlate()          → IncidentReport or None
  6. if None: log parse failure, escalate bare anomaly report
  7. gate_checker.evaluate()         → ActionDecision or EscalationDecision
  8. if ActionDecision:
       executor.execute()            → ActionResult
  9. if EscalationDecision:
       hardware_diagnostics (if needed) → hardware report
       audit_logger.log_escalation() → human_report to SQLite
  10. continue
"""
```

---

## Step 8 — Build the Fault Injection Suite

### 8.1 fault_injection/scenarios/
Each scenario is a class with:
```python
class DiskFillScenario:
    def inject(self, target_percent: float) -> None
    def cleanup(self) -> None
    def verify_injected(self) -> bool
```

Scenarios:
- `disk_fill.py` → `fallocate -l {size} /tmp/fault_fill_{id}`
- `memory_pressure.py` → `stress-ng --vm 1 --vm-bytes {size} --timeout {duration}`
- `cpu_stress.py` → `stress-ng --cpu {cores} --timeout {duration}`
- `zombie_factory.py` → Python subprocess that exits without reaping children
- `log_flood.py` → rapid `logger` calls to journald
- `db_vacuum_starve.py` → CREATE TABLE + INSERT loop on PostgreSQL

For hardware faults (disk, ECC): trigger via the simulator's fault profile injection API rather than real hardware manipulation.

### 8.2 fault_injection/scenario_runner.py
```python
"""
The 47-scenario experimental harness.

For each scenario in SCENARIO_LIST:
  For each repetition in range(5):
    1. Reset system to clean state
    2. Record start time
    3. Inject fault (real or simulator)
    4. Start main_loop
    5. Wait for detection (record MTTD when IncidentReport written)
    6. Wait for resolution (record MTTR when audit_log shows outcome)
    7. Record: TP/FP/FN, confidence score, causal chain accuracy
    8. Cleanup injected fault
    9. 30 second cooldown

Run for each of 3 conditions:
  - no_automation (manual observation only, human records resolution time)
  - rule_based (simple threshold rules → Ansible-style scripted fixes)
  - our_system (full pipeline)
"""
```

---

## Step 9 — Run the Evaluation

### 9.1 evaluation/metrics_recorder.py
Records per-run:
```
scenario_id, repetition, condition, mttd_seconds, mttr_seconds,
true_positive, false_positive, false_negative,
confidence_score, causal_chain_correct, action_taken, action_correct
```

### 9.2 evaluation/wilcoxon_test.py
```python
"""
For each metric (MTTD, MTTR):
  Wilcoxon signed-rank test:
    our_system vs no_automation
    our_system vs rule_based
  Report: W statistic, p-value, effect size (rank-biserial correlation)
  Threshold for significance: p < 0.05
"""
```

### 9.3 Run everything
```bash
# Run full 47-scenario evaluation
python -m fault_injection.scenario_runner --condition our_system --output data/results/our_system.csv
python -m fault_injection.scenario_runner --condition rule_based --output data/results/rule_based.csv

# Statistical analysis
python -m evaluation.wilcoxon_test \
  --our data/results/our_system.csv \
  --baseline data/results/rule_based.csv \
  --output data/results/significance.json

# Generate charts
python -m evaluation.results_plotter --results data/results/ --output docs/figures/
```

---

## Build Order (Strict Sequence)

```
Week 1   Step 0    Codespaces + InfluxDB + environment
Week 1   Step 1    Simulator (SMART, IPMI, ECC) + fault profiles
Week 2   Step 2    Collector (hardware + OS layer + orchestrator)
Week 2   Step 3    Storage (InfluxDB write + SQLite schema)
Week 3   Step 4    Anomaly detection (Z-score → Isolation Forest → SMART acceleration)
Week 4   Step 5    LLM reasoning (schemas → prompt builder → client → parser → correlator)
Week 5   Step 6    Remediation (gates → executor → audit log → hardware diagnostics)
Week 6   Step 7    Pipeline main loop (wire everything together, end-to-end smoke test)
Week 7   Step 8    Fault injection suite (all 7 scenario types)
Week 8   Step 9    Evaluation harness (47 scenarios × 5 reps × 3 conditions)
Week 9            Notebooks: results analysis, charts, significance tests
Week 10           Write paper sections: methodology, results, discussion
```

---

## Verification Checkpoints

After each step, verify before moving on:

| Step | Verification |
|------|-------------|
| 1 — Simulator | `python -c "from simulator.smart_simulator import SmartSimulator; s = SmartSimulator('disk_failing'); print(s.get_reading())"` returns valid SMART dict |
| 2 — Collector | `python -m collector.orchestrator` prints unified snapshot with all sources |
| 3 — Storage | InfluxDB UI at localhost:8086 shows incoming telemetry data |
| 4 — Anomaly | `pytest tests/unit/test_anomaly_detectors.py` all pass |
| 5 — LLM | `python -m reasoning.correlator --test` returns valid IncidentReport JSON |
| 6 — Remediation | `pytest tests/unit/test_gate_checker.py tests/unit/test_executor.py` all pass |
| 7 — Pipeline | Inject disk_fill → main_loop detects within 2 poll intervals → audit log shows entry |
| 8 — Injection | Each scenario class: `inject()` → `verify_injected()` → `cleanup()` all pass |
| 9 — Evaluation | result CSV has correct shape, Wilcoxon runs without errors |

---

## Key Design Decisions Already Made

- **No Docker** — agent runs as native Python process, systemd service file provided
- **No Ansible** — executor uses direct subprocess with sudoers whitelist
- **Claude API** for LLM during development — one-line swap to Ollama client for production target
- **MODE=simulate** env var switches entire telemetry layer between real and simulated
- **InfluxDB** for time-series, **SQLite** for incidents and audit — no shared database server required
- **pydantic** validation is the hard barrier between LLM output and any executable action
- **Backblaze dataset** calibrates SMART simulator — cite this in the paper's methodology section
