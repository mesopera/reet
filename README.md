# Reet
# An Autonomous Server Healing System

An LLM-augmented autonomous fault detection, remediation, and hardware diagnostic framework for bare-metal Linux servers in resource-constrained environments.

---

## Overview

This system operates as a lightweight daemon that continuously collects telemetry from bare-metal Linux servers, detects anomalies using a multi-method statistical pipeline, uses an LLM to reason across signals from multiple system layers, and either auto-remediates software-fixable faults or generates plain-language hardware repair instructions for human operators.

**Key results from experimental evaluation:**
- 94.4% reduction in Mean Time to Detect (MTTD) vs no automation (50.4s vs 900s)
- 98.6% reduction in Mean Time to Remediate (MTTR) vs no automation (51.3s vs 3600s)
- 93.8% detection rate across 13 fault scenarios × 5 repetitions
- Zero false positives across all 65 experimental runs
- All improvements statistically significant at p < 0.0001 (Wilcoxon signed-rank test)

---

## Table of Contents

- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Running the System](#running-the-system)
- [Fault Injection and Evaluation](#fault-injection-and-evaluation)
- [Project Structure](#project-structure)
- [How It Works](#how-it-works)
- [Tech Stack](#tech-stack)
- [Limitations](#limitations)
- [Research Context](#research-context)

---

## Architecture

```
INPUT                COLLECT              REASON              GATE                OUTPUT
─────────────────────────────────────────────────────────────────────────────────────────
IPMI / iDRAC    →                    →                   → Confidence ≥ 0.75  → Auto-Fix
SMART Data      →  Telemetry         →  LLM Cross-Layer  → Fault whitelisted  → (+ audit log)
MCE / ECC Logs  →  Collection        →  Causal           → No hardware fault  →
/proc & /sys    →  Engine            →  Reasoning        →                    → Human Report
journald/dmesg  →  (parallel,        →  (Llama 3.1 8B)  →                    → (plain language
DB interfaces   →   timestamped)     →                   →                    →  repair guide)
                         ↓
                  Anomaly Detection
                  ─────────────────
                  Z-score detector
                  Isolation Forest
                  Seasonal baseline
                  SMART acceleration  ← Novel: derivative-based, not threshold-based
                  ECC rate model
```

If any gate fails → escalate immediately, no action taken.

---

## Prerequisites

- Python 3.11+
- Ubuntu 22.04 LTS (or GitHub Codespaces with the included devcontainer)
- A [Groq API key](https://console.groq.com) (free tier is sufficient)
- InfluxDB 2.7+ running locally
- stress-ng (for fault injection evaluation only)

---

## Quick Start

### 1. Clone and open in Codespaces

```bash
git clone https://github.com/yourusername/autonomous-server-healing
```

Open in GitHub Codespaces: **Code → Codespaces → New codespace** (select 4-core 16GB machine).

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Install and start InfluxDB

```bash
wget https://dl.influxdata.com/influxdb/releases/influxdb2-2.7.10_linux_amd64.tar.gz
tar xzf influxdb2-2.7.10_linux_amd64.tar.gz
sudo cp influxdb2-2.7.10/usr/bin/influxd /usr/local/bin/
influxd &
sleep 3
```

Open InfluxDB UI at port 8086, complete setup with:
- Organization: `healing-system`
- Bucket: `telemetry`
- Copy the generated token

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in:
# GROQ_API_KEY=your_groq_key
# INFLUX_TOKEN=your_influxdb_token
```

### 5. Run the pipeline

```bash
python -m pipeline.main_loop
```

---

## Configuration

### `.env`

| Variable | Description | Default |
|---|---|---|
| `GROQ_API_KEY` | Groq API key for LLM inference | required |
| `INFLUX_URL` | InfluxDB URL | `http://localhost:8086` |
| `INFLUX_TOKEN` | InfluxDB auth token | required |
| `INFLUX_ORG` | InfluxDB organization | `healing-system` |
| `INFLUX_BUCKET` | InfluxDB bucket | `telemetry` |
| `SQLITE_PATH` | SQLite incident database path | `data/incidents.db` |
| `SNAPSHOT_DIR` | Pre-action state snapshot directory | `data/snapshots` |
| `MODE` | `simulate` or `live` | `simulate` |
| `LLM_CONFIDENCE_THRESHOLD` | Minimum confidence for auto-remediation | `0.75` |
| `POLL_INTERVAL_SECONDS` | Telemetry collection interval | `60` |

### `config/settings.yaml`

Tune anomaly detection thresholds, Z-score windows, Isolation Forest contamination factor, SMART acceleration sensitivity, and LLM model selection.

### `config/whitelist.yaml`

Defines which actions the system is permitted to execute autonomously. Each action entry specifies:
- Allowed fault categories
- Parameter validation regex
- Whether sudo is required
- Whether the action is reversible

**Current whitelisted actions:**
- `restart_service` — restart a failed systemd unit
- `vacuum_logs` — truncate journal logs to free disk space
- `reap_zombies` — signal parents of zombie processes
- `trigger_vacuum` — run PostgreSQL VACUUM ANALYZE

---

## Running the System

### Simulate mode (default — no real hardware needed)

```bash
MODE=simulate python -m pipeline.main_loop
```

Telemetry is generated by the simulator using calibrated fault profiles. Real `/proc`, `/sys`, and `journald` data is still collected from the live OS.

### Live mode (bare-metal Linux server)

```bash
MODE=live python -m pipeline.main_loop
```

Requires `ipmitool`, `smartmontools`, and `rasdaemon` installed. The collector falls back gracefully if any source is unavailable.

### Fast-cycle testing

```bash
POLL_INTERVAL_SECONDS=3 python -m pipeline.main_loop
```

### Inject a specific fault profile

Change the fault profile in the simulator section of `config/settings.yaml` or set it directly:

```bash
# In Python
from simulator.smart_simulator import SmartSimulator
sim = SmartSimulator('disk_failing_slow')
```

Available profiles in `simulator/fault_profiles/`:
- `healthy_baseline.yaml`
- `disk_failing_slow.yaml` — reallocated sectors accelerating over 72 hours
- `disk_failing_fast.yaml` — same over 12 hours
- `memory_degrading.yaml` — ECC errors doubling every 8 hours
- `cpu_thermal.yaml` — CPU temperature escalating
- `psu_unstable.yaml` — PSU voltage ripple
- `fan_failure.yaml` — fan RPM dropping to zero

---

## Fault Injection and Evaluation

### Run a single scenario test

```bash
python -m fault_injection.scenario_runner --scenario S01 --condition our_system --reps 1
```

Available scenario IDs: S01–S13 (see Table 1 in the paper).

### Run full evaluation (all 3 conditions)

```bash
# Our system (~30 minutes)
python -m fault_injection.scenario_runner \
  --condition our_system \
  --output data/results/our_system.csv \
  --reps 5

# No automation baseline (fast — uses fixed representative times)
python -m evaluation.baseline_runner \
  --condition no_automation \
  --output data/results/no_automation.csv \
  --reps 5

# Rule-based baseline (fast)
python -m evaluation.baseline_runner \
  --condition rule_based \
  --output data/results/rule_based.csv \
  --reps 5
```

### Statistical analysis and plots

```bash
# Wilcoxon signed-rank test
python -m evaluation.wilcoxon_test \
  --our data/results/our_system.csv \
  --no_auto data/results/no_automation.csv \
  --rule data/results/rule_based.csv

# Generate figures for paper
python -m evaluation.results_plotter \
  --our data/results/our_system.csv \
  --no_auto data/results/no_automation.csv \
  --rule data/results/rule_based.csv \
  --output docs/figures/
```

### Query the audit log

```bash
# View all incidents
sqlite3 data/incidents.db "SELECT detected_at, root_cause, confidence, fault_category, action_taken FROM incidents ORDER BY detected_at DESC LIMIT 20;"

# View audit trail for a specific incident
sqlite3 data/incidents.db "SELECT timestamp, event_type, detail FROM audit_log WHERE incident_id='<id>';"

# Count by fault category
sqlite3 data/incidents.db "SELECT fault_category, COUNT(*) FROM incidents GROUP BY fault_category;"
```

---

## Project Structure

```
autonomous-server-healing/
│
├── simulator/                    # Telemetry simulator (calibrated against Backblaze dataset)
│   ├── smart_simulator.py        # SMART attribute stream with fault profiles
│   ├── ipmi_simulator.py         # IPMI sensor stream
│   ├── ecc_simulator.py          # ECC error count stream
│   ├── backblaze_loader.py       # Loads calibration parameters from Backblaze data
│   └── fault_profiles/           # YAML fault profile definitions
│
├── collector/                    # Telemetry collection layer
│   ├── orchestrator.py           # Parallel collection, shared timestamps
│   ├── hardware/                 # SMART, IPMI, ECC collectors
│   ├── os_layer/                 # /proc, /sys, disk collectors
│   ├── services/                 # journald, process collectors
│   └── database/                 # PostgreSQL collector
│
├── storage/                      # Persistence layer
│   ├── influx_client.py          # InfluxDB time-series write/query
│   ├── incident_store.py         # SQLite incident + audit log CRUD
│   └── schema.sql                # SQLite schema definition
│
├── anomaly/                      # Multi-method anomaly detection
│   ├── zscore_detector.py        # Rolling window Z-score
│   ├── isolation_forest.py       # Multivariate Isolation Forest
│   ├── seasonal_baseline.py      # STL seasonal decomposition
│   ├── smart_acceleration.py     # Novel: derivative-based SMART detection
│   ├── ecc_rate_model.py         # ECC error acceleration model
│   └── anomaly_aggregator.py     # Aggregates all detectors → AnomalyReport
│
├── reasoning/                    # LLM reasoning layer
│   ├── llm_client.py             # Groq/Llama 3.1 8B API wrapper
│   ├── prompt_builder.py         # Structured prompt construction
│   ├── response_parser.py        # JSON extraction + Pydantic validation
│   ├── schemas.py                # IncidentReport, CausalStep Pydantic models
│   └── correlator.py             # Orchestrates anomaly → LLM → IncidentReport
│
├── remediation/                  # Safety-gated remediation engine
│   ├── gate_checker.py           # Three-gate safety model
│   ├── executor.py               # Whitelisted action execution
│   ├── snapshot.py               # Pre-action state capture
│   ├── audit_logger.py           # Append-only audit trail
│   └── actions/                  # Individual action handlers
│       ├── restart_service.py
│       ├── vacuum_logs.py
│       ├── reap_zombies.py
│       └── trigger_vacuum.py
│
├── hardware_diagnostics/         # Hardware failure analysis
│   ├── component_localizer.py    # Maps fault to physical component/slot
│   ├── urgency_model.py          # Acceleration-based urgency tier
│   ├── vendor_lookup.py          # Vendor SMART table + replacement guidance
│   └── report_generator.py      # Plain-language repair report (LLM-generated)
│
├── fault_injection/              # Experimental fault injection suite
│   ├── scenario_runner.py        # 13-scenario evaluation harness
│   └── scenarios/                # Individual scenario classes
│       ├── disk_fill.py          # fallocate disk exhaustion
│       ├── memory_pressure.py    # stress-ng memory hog
│       ├── cpu_stress.py         # stress-ng CPU load
│       ├── zombie_factory.py     # Orphaned process accumulation
│       ├── log_flood.py          # journald log flood
│       ├── nfs_hang_sim.py       # NFS timeout simulation
│       └── db_vacuum_starve.py   # PostgreSQL dead tuple bloat
│
├── evaluation/                   # Results analysis
│   ├── metrics_recorder.py       # Precision, recall, F1, MTTD, MTTR
│   ├── baseline_runner.py        # No-automation and rule-based baselines
│   ├── wilcoxon_test.py          # Statistical significance testing
│   └── results_plotter.py        # matplotlib/seaborn result charts
│
├── pipeline/
│   └── main_loop.py              # Master control loop
│
├── tests/
│   ├── unit/                     # Unit tests per module
│   ├── integration/              # Cross-module integration tests
│   └── e2e/                      # Full pipeline end-to-end tests
│
├── config/
│   ├── settings.yaml             # Thresholds, model config, intervals
│   ├── whitelist.yaml            # Approved autonomous actions
│   └── vendor_smart_tables.json  # Vendor SMART attribute maps
│
├── data/
│   ├── backblaze/                # Backblaze dataset (gitignored, download separately)
│   ├── results/                  # Experiment result CSVs
│   └── snapshots/                # Pre-action snapshots (gitignored)
│
├── docs/
│   └── figures/                  # Generated evaluation charts
│
├── notebooks/
│   ├── 01_backblaze_exploration.ipynb
│   ├── 02_smart_acceleration_model.ipynb
│   ├── 03_isolation_forest_tuning.ipynb
│   └── 04_results_analysis.ipynb
│
├── .env.example
├── .devcontainer/devcontainer.json
├── requirements.txt
└── README.md
```

---

## How It Works

### 1. Collection (every N seconds)

All collectors run in parallel via `ThreadPoolExecutor`. Every reading in a cycle shares a single `run_id` and `timestamp`. This shared timestamp is what enables temporal causal ordering — the LLM can determine that a DIMM error at T=0 preceded a process crash at T=4s, establishing causality.

### 2. Anomaly Detection

Four detectors run on every collection snapshot:

| Detector | Method | What it catches |
|---|---|---|
| Z-score | Rolling window mean ± N·σ | Sudden spikes in any single metric |
| Isolation Forest | Unsupervised ensemble | Unusual multivariate combinations |
| Seasonal baseline | STL decomposition | Deviations from time-of-day pattern |
| SMART acceleration | First + second derivative | Developing hardware failures (novel) |

Only flagged signals are passed to the LLM — raw telemetry never touches the LLM directly.

### 3. LLM Reasoning

Flagged signals are assembled into a structured prompt alongside server context and 6-hour metric history. The LLM (Llama 3.1 8B via Groq) produces a JSON incident report validated by Pydantic. If the output fails validation, the system escalates immediately — it never acts on unvalidated LLM output.

### 4. Three-Gate Safety Model

```
Incident → Gate 1: confidence ≥ threshold?
               ↓ YES
           Gate 2: action on whitelist?
               ↓ YES
           Gate 3: hardware_involved == False?
               ↓ YES
           Execute action → snapshot → audit log
               ↓ NO (any gate)
           Escalate → human report → audit log
```

### 5. Hardware Diagnostics (on hardware faults)

1. Urgency model fits acceleration curve → estimates time-to-failure window
2. Component localiser identifies physical location (slot, bay, port)
3. Vendor lookup maps drive model to vendor-specific SMART interpretation
4. LLM generates plain-language repair report with step-by-step instructions

---

## Tech Stack

| Layer | Tool | Why |
|---|---|---|
| Language | Python 3.11 | ML ecosystem + system scripting |
| LLM | Llama 3.1 8B via Groq | Production target model, free API |
| Output validation | Pydantic | Hard barrier between LLM and action |
| Hardware sensors | ipmitool | BMC/IPMI access independent of OS |
| Drive health | smartmontools | Universal SMART polling |
| Memory errors | rasdaemon | Kernel MCE log collection |
| Anomaly detection | scikit-learn, statsmodels, scipy | Isolation Forest, STL, curve fitting |
| Time-series storage | InfluxDB 2.7 | Purpose-built for telemetry |
| Incident storage | SQLite | Lightweight, no external server |
| Fault injection | stress-ng, fallocate | CPU/memory/disk fault simulation |
| Statistical testing | scipy.stats | Wilcoxon signed-rank test |

---

## Limitations

- **Hardware telemetry is simulated** in this implementation. The simulator is calibrated against the Backblaze Hard Drive Dataset but is not equivalent to real hardware fault injection. The `MODE=live` switch enables real hardware collection but requires appropriate server hardware.
- **SMART acceleration requires 10+ readings** before scoring begins. At a 60-second poll interval this is a ~10 minute warm-up window.
- **Isolation Forest requires 200 readings** before the model is trained. At 60-second intervals this is a ~3.3 hour cold-start window.
- **Whitelist is deliberately conservative.** Four action types cover common software-layer faults but do not cover the full space of possible server faults. Recall is bounded by whitelist coverage.
- **LLM inference latency** via Groq API adds 2--8 seconds to each detection cycle. On-premise inference will be slower depending on available hardware.

---

## Research Context

This system was built as a research prototype targeting Scopus-indexed publication. The codebase is the experimental implementation supporting the paper:

> "Autonomous Fault Detection, Remediation and Hardware Diagnostics for Bare-Metal Linux Servers in Resource-Constrained Environments"

**Target venues:** Journal of Systems and Software (Elsevier), Future Generation Computer Systems (Elsevier), IEEE Access

**Evaluation dataset:** Available in `data/results/` — three CSVs covering our system, no-automation baseline, and rule-based baseline across 13 scenarios × 5 repetitions × 3 conditions.

**Reproducing results:**

```bash
# Run full evaluation
python -m fault_injection.scenario_runner --condition our_system --output data/results/our_system.csv --reps 5
python -m evaluation.baseline_runner --condition no_automation --output data/results/no_automation.csv --reps 5
python -m evaluation.baseline_runner --condition rule_based --output data/results/rule_based.csv --reps 5

# Statistical analysis
python -m evaluation.wilcoxon_test \
  --our data/results/our_system.csv \
  --no_auto data/results/no_automation.csv \
  --rule data/results/rule_based.csv
```

---

## License

MIT License. See LICENSE for details.