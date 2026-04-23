## Complete Project Execution Plan

---

## PHASE 0 — Environment Setup
*Do this once. Everything else builds on it.*

**0.1 GitHub Repository**
- Create new repo on GitHub: `autonomous-server-healing`
- Choose Python `.gitignore` and MIT license
- Clone locally or open directly in Codespaces

**0.2 Launch Codespaces**
- Go to repo → Code → Codespaces → New codespace
- Select 4-core 16GB machine (free tier is enough, no GPU needed)
- Wait for it to boot into VS Code browser

**0.3 Create `.devcontainer/devcontainer.json`**
- Python 3.11 base image
- `postCreateCommand` to install requirements and copy `.env.example` to `.env`
- Forward ports 8086 (InfluxDB) and 8888 (Jupyter)

**0.4 Create the full directory structure**
- Create every folder and `__init__.py` file as per the scaffold
- Commit the empty structure immediately

**0.5 Create `requirements.txt` and install**
- `anthropic`, `pandas`, `numpy`, `scipy`, `scikit-learn`, `statsmodels`
- `influxdb-client`, `SQLAlchemy`, `pydantic`, `pyyaml`
- `psycopg2-binary`, `matplotlib`, `seaborn`
- `pytest`, `pytest-cov`, `python-dotenv`, `black`
- Run `pip install -r requirements.txt`

**0.6 Install and configure InfluxDB**
- Download InfluxDB 2.x Linux binary
- Copy binary to `/usr/local/bin/influxd`
- Run `influxd &` to start in background
- Run `influx setup` to create org `healing-system`, bucket `telemetry`
- Copy the generated token

**0.7 Create `.env` and `.env.example`**
- `ANTHROPIC_API_KEY` — paste your key
- `INFLUX_URL=http://localhost:8086`
- `INFLUX_TOKEN` — paste token from InfluxDB setup
- `INFLUX_ORG=healing-system`
- `INFLUX_BUCKET=telemetry`
- `SQLITE_PATH=data/incidents.db`
- `SNAPSHOT_DIR=data/snapshots`
- `MODE=simulate`
- `LLM_CONFIDENCE_THRESHOLD=0.75`
- `POLL_INTERVAL_SECONDS=60`
- Add `.env` to `.gitignore`, commit `.env.example`

**0.8 Create `config/settings.yaml`**
- Poll interval, confidence threshold
- Z-score threshold per metric category
- Isolation Forest contamination factor
- SMART acceleration threshold values
- Log level

**0.9 Create `config/whitelist.yaml`**
- `restart_service` action entry with parameter regex
- `vacuum_logs` action entry
- `reap_zombies` action entry
- `trigger_vacuum` action entry

**0.10 Create `config/vendor_smart_tables.json`**
- Vendor-specific SMART attribute mappings for WD, Seagate, Samsung, Toshiba
- Maps attribute IDs to human-readable names and failure thresholds

**0.11 Verify environment**
- `python --version` → 3.11
- `python -c "import anthropic; print('ok')"` → ok
- `influx ping` → ok
- `pytest --version` → ok

---

## PHASE 1 — Backblaze Dataset + Simulator Calibration
*This is what makes your telemetry believable.*

**1.1 Download Backblaze Hard Drive Dataset**
- Go to `backblaze.com/cloud-storage/resources/hard-drive-test-data`
- Download Q4 2023 data (latest available)
- Unzip into `data/backblaze/`
- Files are daily CSVs with SMART readings for every drive in Backblaze's data centers

**1.2 Create `notebooks/01_backblaze_exploration.ipynb`**
- Load a sample of the CSVs into a DataFrame
- Filter to drives that failed (`failure == 1`) within 30/60/90 days
- Plot SMART attribute 5 (reallocated sectors), 187, 197, 198 over time for failing drives
- Identify which attributes show the clearest pre-failure signal
- Note the typical acceleration curve shape (exponential vs linear)

**1.3 Create `notebooks/02_smart_acceleration_model.ipynb`**
- For the top 3 failure-predictive SMART attributes, fit an exponential curve to pre-failure trajectories
- Extract median `A` (initial amplitude) and `k` (growth rate) parameters
- These parameters become the defaults in your simulator fault profiles
- Save fitted parameters to `data/backblaze/calibration_params.json`

**1.4 Create `simulator/backblaze_loader.py`**
- Loads the calibration params JSON
- Provides `get_failure_curve(attribute_id, drive_model)` → returns `(A, k, noise_std)`
- Used by the SMART simulator to generate realistic fault trajectories

**1.5 Create `simulator/fault_profiles/*.yaml`**
- `healthy_baseline.yaml` — stable SMART values, normal IPMI readings, zero ECC errors
- `disk_failing_slow.yaml` — reallocated sectors accelerating over 72 hours
- `disk_failing_fast.yaml` — same but over 12 hours (imminent failure)
- `memory_degrading.yaml` — ECC correctable errors doubling every 8 hours
- `cpu_thermal.yaml` — CPU temperature escalating beyond 85°C
- `psu_unstable.yaml` — 12V rail rippling ±0.8V
- `fan_failure.yaml` — single fan RPM → 0

**1.6 Create `simulator/smart_simulator.py`**
- Class `SmartSimulator(fault_profile: str)`
- Loads the specified fault profile YAML
- `get_reading()` → returns dict matching `smartctl -x --json` output schema
- Internal state: current attribute values, elapsed time steps
- `inject_fault(fault_type, start_offset_hours)` → begins degradation curve from that point
- Uses calibration params from backblaze_loader for realistic curves
- Adds Gaussian noise to every attribute every reading

**1.7 Create `simulator/ipmi_simulator.py`**
- Class `IpmiSimulator(fault_profile: str)`
- `get_reading()` → returns list of sensor dicts matching `ipmitool sdr list` format
- Each sensor: name, value, unit, status (`ok` / `nc` / `cr`)
- Fault modes: `cpu_thermal` escalates CPU temp sensor, `fan_failure` drops fan RPM to 0

**1.8 Create `simulator/ecc_simulator.py`**
- Class `EccSimulator(fault_profile: str)`
- `get_reading()` → returns dict with `ce_count` (correctable errors), `ue_count` (uncorrectable)
- Healthy: ce_count 0–2 per hour, Poisson distributed
- Degrading: ce_count follows exponential growth model fitted from literature

**1.9 Write unit tests `tests/unit/test_smart_simulator.py`**
- Test: healthy profile returns values within normal ranges
- Test: disk_failing profile shows increasing attribute 5 over 10 time steps
- Test: second derivative of attribute 5 is positive in failing mode
- Test: output dict has all required SMART fields

**1.10 Verify Phase 1**
```bash
pytest tests/unit/test_smart_simulator.py -v
python -c "
from simulator.smart_simulator import SmartSimulator
s = SmartSimulator('disk_failing_slow')
for i in range(5):
    r = s.get_reading()
    print(r['smart_attributes']['reallocated_sector_ct']['raw_value'])
"
# Should show increasing values
```

---

## PHASE 2 — Collector Layer
*Real /proc and /sys data. Simulated hardware data. Unified interface.*

**2.1 Create `collector/base_collector.py`**
- `TelemetryReading` dataclass: source, component, metric, value, unit, timestamp, raw dict
- `BaseCollector` abstract class with `collect() → list[TelemetryReading]`

**2.2 Create `collector/hardware/smart_collector.py`**
- In `simulate` mode: instantiates SmartSimulator and calls `get_reading()`
- In `live` mode: runs `smartctl -x --json /dev/sda` via subprocess, parses JSON
- Converts output to list of `TelemetryReading` objects (one per SMART attribute)
- Handles `smartctl` not found gracefully (logs warning, returns empty list)

**2.3 Create `collector/hardware/ipmi_collector.py`**
- In `simulate` mode: uses IpmiSimulator
- In `live` mode: runs `ipmitool sdr list` via subprocess, parses text output
- Returns TelemetryReading per sensor

**2.4 Create `collector/hardware/ecc_collector.py`**
- In `simulate` mode: uses EccSimulator
- In `live` mode: reads `/sys/devices/system/edac/mc0/ce_count` and `ue_count`
- Falls back to rasdaemon log parsing if sysfs path not found

**2.5 Create `collector/os_layer/proc_collector.py`**
- Reads real `/proc/meminfo` → extracts MemTotal, MemFree, MemAvailable, SwapUsed
- Reads real `/proc/loadavg` → 1min, 5min, 15min load averages
- Reads real `/proc/stat` → CPU user/system/idle percentages
- Reads real `/proc/vmstat` → page fault counts, swap in/out
- Returns TelemetryReading per metric

**2.6 Create `collector/os_layer/sys_collector.py`**
- Reads `/sys/block/sda/stat` → read/write ops, sectors, wait times
- Reads `/sys/class/net/eth0/statistics/` → tx/rx bytes, errors, dropped packets
- Returns TelemetryReading per metric

**2.7 Create `collector/os_layer/disk_collector.py`**
- Uses `shutil.disk_usage()` for each mounted filesystem
- Returns: total, used, free, percent used per mount point
- Also reads inode usage via `os.statvfs()`

**2.8 Create `collector/services/journald_collector.py`**
- Uses `subprocess` to run `journalctl --since="5 minutes ago" --output=json`
- Parses JSON log lines
- Counts: error lines per unit, warning lines per unit, restart events
- Returns TelemetryReading per unit with error count as value

**2.9 Create `collector/services/process_collector.py`**
- Reads `/proc/<pid>/status` for all running processes
- Identifies zombie processes (`State: Z`)
- Counts processes per state, memory per process for top consumers
- Returns TelemetryReading per metric

**2.10 Create `collector/database/postgres_collector.py`**
- Connects via psycopg2 (uses `postgres` db if available, skips gracefully if not)
- Queries `pg_stat_activity` → active connections, idle connections, long-running queries
- Queries `pg_stat_bgwriter` → checkpoint stats, buffer writes
- Queries `pg_stat_user_tables` → dead tuples count (bloat indicator)
- Returns TelemetryReading per metric

**2.11 Create `collector/orchestrator.py`**
- Instantiates all collectors
- Runs all `collect()` calls concurrently using `ThreadPoolExecutor(max_workers=8)`
- Assigns a shared `run_id = uuid4()` and common `timestamp = datetime.utcnow()` to all readings
- Aggregates into a single `CollectionSnapshot` object
- Logs total readings collected and any collector errors (does not crash on partial failure)

**2.12 Write unit tests `tests/unit/test_collectors.py`**
- Test: proc_collector returns non-empty list with correct field types
- Test: orchestrator returns snapshot with readings from at least 3 sources
- Test: all TelemetryReading timestamps in a snapshot are identical
- Test: collector failure does not crash orchestrator

**2.13 Verify Phase 2**
```bash
pytest tests/unit/test_collectors.py -v
python -m collector.orchestrator
# Should print: "Collected N readings from M sources in X.Xs"
```

---

## PHASE 3 — Storage Layer
*Write telemetry to InfluxDB. Write incidents to SQLite.*

**3.1 Create `storage/influx_client.py`**
- Wraps `influxdb_client.InfluxDBClient`
- `write(readings: list[TelemetryReading])` → writes as InfluxDB line protocol points
  - Measurement = `reading.source`
  - Tags = `component`, `metric`
  - Field = `value`
  - Time = `reading.timestamp`
- `query_range(metric, component, start_hours_ago, end_hours_ago=0)` → returns `pd.DataFrame`
- `query_latest(metric, component)` → returns single `TelemetryReading`
- Handles connection errors with retry (3 attempts, exponential backoff)

**3.2 Create `storage/schema.sql`**
- `incidents` table as defined in scaffold
- `audit_log` table as defined in scaffold
- Run once on startup to create tables if not exist

**3.3 Create `storage/incident_store.py`**
- On init: creates SQLite connection, runs `schema.sql`
- `save_incident(incident: IncidentReport)` → INSERT into incidents
- `save_audit_event(incident_id, event_type, detail)` → INSERT into audit_log
- `get_incident(id)` → SELECT + return dict
- `list_incidents(limit=50)` → SELECT recent incidents
- All writes use transactions, never lose a record

**3.4 Write unit tests `tests/unit/test_storage.py`**
- Test: influx write then query_latest returns the written value
- Test: incident_store save then get returns same data
- Test: audit_log entries linked to correct incident

**3.5 Integration test `tests/integration/test_collect_to_storage.py`**
- Run orchestrator → write to InfluxDB → query back → verify values match

**3.6 Verify Phase 3**
```bash
pytest tests/unit/test_storage.py tests/integration/test_collect_to_storage.py -v
# Open InfluxDB UI at localhost:8086 → verify data appears in telemetry bucket
```

---

## PHASE 4 — Anomaly Detection Layer
*Filter the stream. Only send real signals to the LLM.*

**4.1 Create `anomaly/zscore_detector.py`**
- Maintains rolling deque of last N values per (component, metric) key
- `update(reading: TelemetryReading)` → adds to deque
- `score(reading: TelemetryReading)` → returns z-score float
- `is_anomalous(reading, threshold=3.0)` → returns bool
- Minimum window size before scoring: 10 readings (avoid false positives on startup)

**4.2 Create `anomaly/isolation_forest.py`**
- Collects first 200 readings per source as warm-up (training data)
- After warm-up: fits `IsolationForest(contamination=0.05)`
- `score(snapshot: CollectionSnapshot)` → returns anomaly scores per reading
- Re-trains every 1000 readings on sliding window
- State is persisted to disk (joblib pickle) so re-training survives restarts

**4.3 Create `anomaly/seasonal_baseline.py`**
- Queries InfluxDB for last 7 days of a given metric
- Runs `seasonal_decompose(data, period=1440)` (1440 minutes = 1 day seasonality)
- Stores the seasonal component as the "expected" baseline
- `expected_value(metric, component, timestamp)` → returns baseline value for that time
- `deviation(reading)` → returns `(actual - expected) / expected` as percentage deviation

**4.4 Create `anomaly/smart_acceleration.py`**
- `compute_acceleration(metric, component)`:
  - Queries last 72 hours from InfluxDB for this (metric, component) pair
  - Requires minimum 10 readings to compute
  - Computes first derivative: `np.diff(values) / np.diff(timestamps_in_hours)`
  - Computes second derivative: `np.diff(first_derivative)`
  - Returns `AccelerationResult(first_deriv, second_deriv, is_accelerating, urgency_score)`
- `urgency_score` = `second_deriv[-1] * abs(current_value)` — fast-growing high-value = urgent
- Only runs on SMART attributes that are failure-predictive (IDs 5, 187, 188, 197, 198)

**4.5 Create `anomaly/ecc_rate_model.py`**
- Same structure as smart_acceleration but for ECC ce_count
- Window: last 24 hours
- Flags if rate has doubled within any 8-hour window
- Returns `EccRateResult(current_rate_per_hour, doubling_time_hours, is_accelerating)`

**4.6 Create `anomaly/anomaly_aggregator.py`**
- `run(snapshot: CollectionSnapshot)` → `AnomalyReport`
- For each reading: run z-score detector, update isolation forest
- Run SMART acceleration on SMART readings
- Run ECC rate model on ECC readings
- Run seasonal deviation on OS metrics
- Aggregates all flagged signals into `AnomalyReport`:
  ```python
  @dataclass
  class FlaggedSignal:
      source: str
      component: str
      metric: str
      value: float
      anomaly_type: str   # 'zscore_spike', 'isolation_forest', 'smart_acceleration', 'ecc_rate'
      severity: float     # 0.0 – 1.0
      details: dict       # z-score value, acceleration rate, etc.

  @dataclass
  class AnomalyReport:
      run_id: str
      timestamp: datetime
      flagged_signals: list[FlaggedSignal]
      total_readings_scanned: int
  ```
- Returns AnomalyReport (empty flagged_signals list if nothing is anomalous)

**4.7 Write unit tests `tests/unit/test_anomaly_detectors.py`**
- Test zscore: 10 normal readings then one 5-sigma spike → flagged
- Test zscore: all normal readings → not flagged
- Test smart_acceleration: flat data → not accelerating
- Test smart_acceleration: exponential data → is_accelerating = True, urgency > 0
- Test ecc_rate: stable ECC counts → not flagged
- Test ecc_rate: doubling counts → is_accelerating = True
- Test aggregator: healthy simulator readings → empty flagged_signals
- Test aggregator: disk_failing simulator readings → at least one flagged signal

**4.8 Tune detection thresholds**
- Run `notebooks/03_isolation_forest_tuning.ipynb`
- Generate 1000 healthy readings + inject 50 fault readings
- Sweep contamination parameter 0.01–0.1, plot precision/recall
- Select contamination value that gives precision > 0.90
- Update `config/settings.yaml` with tuned values

**4.9 Verify Phase 4**
```bash
pytest tests/unit/test_anomaly_detectors.py -v

# Smoke test: run simulator in fault mode, check anomaly fires
python -c "
from simulator.smart_simulator import SmartSimulator
from collector.hardware.smart_collector import SmartCollector
from anomaly.anomaly_aggregator import AnomalyAggregator
import os; os.environ['MODE'] = 'simulate'

sim = SmartSimulator('disk_failing_slow')
col = SmartCollector(simulator=sim)
agg = AnomalyAggregator()

for i in range(20):
    readings = col.collect()
    report = agg.run(readings)
    print(f'Step {i}: {len(report.flagged_signals)} flags')
"
# Should show 0 flags early, then flags appearing as fault develops
```

---

## PHASE 5 — LLM Reasoning Layer
*The brain of the system.*

**5.1 Create `reasoning/schemas.py`**
- `CausalStep` pydantic model: timestamp_offset_seconds, component, event, caused_by
- `IncidentReport` pydantic model: root_cause, root_cause_component, confidence (0–1), fault_category, hardware_involved, causal_chain, auto_remediable, suggested_action, plain_language_summary, reasoning
- `EscalationReport` pydantic model: reason, anomaly_report_json, recommended_human_actions
- Add field validators: confidence must be 0.0–1.0, fault_category must be in allowed list

**5.2 Create `reasoning/prompt_builder.py`**
- `build_system_prompt()` → returns the system prompt string
  - Role definition
  - Output format: strict JSON only, no markdown, no preamble
  - Paste full IncidentReport JSON schema
  - Rules: never infer hardware fault without sensor evidence, always populate all fields
- `build_user_message(anomaly_report, system_context, recent_history)` → returns user message string
  - `system_context`: hostname, OS version, uptime, running services list, disk/memory usage summary
  - `anomaly_report`: flagged signals as formatted JSON block
  - `recent_history`: last 6 hours of relevant metric trends (queried from InfluxDB), summarised as key stats

**5.3 Create `reasoning/llm_client.py`**
- Loads `ANTHROPIC_API_KEY` from env
- `call_llm(system_prompt, user_message)` → returns raw string response
- Uses `claude-sonnet-4-5` model, `max_tokens=2000`
- Retry logic: 3 attempts on rate limit errors with exponential backoff
- Logs token usage per call to audit log

**5.4 Create `reasoning/response_parser.py`**
- `parse(raw_response: str)` → `IncidentReport | None`
- Strip markdown code fences if present (LLMs sometimes wrap JSON in ```json)
- `json.loads()` the cleaned string
- `IncidentReport.model_validate(parsed_dict)` — pydantic validation
- On any exception: log the raw response and the error, return `None`
- Never raise — always return None on failure

**5.5 Create `reasoning/correlator.py`**
- `correlate(anomaly_report: AnomalyReport, influx_client, system_context)` → `IncidentReport | None`
- Queries InfluxDB for recent history of flagged metrics (last 6 hours)
- Calls `prompt_builder.build_system_prompt()` and `build_user_message()`
- Calls `llm_client.call_llm()`
- Calls `response_parser.parse()`
- If parse returns None: saves escalation record to SQLite, returns None
- If parse returns IncidentReport: saves to SQLite, returns it
- Logs prompt + response to audit_log for every call (critical for paper)

**5.6 Write unit tests `tests/unit/test_prompt_builder.py`**
- Test: system prompt contains the word "JSON" and contains "confidence"
- Test: user message contains all flagged signal fields
- Test: system prompt contains the full IncidentReport schema

**5.7 Write unit tests `tests/unit/test_response_parser.py`**
- Test: valid JSON matching schema → returns IncidentReport
- Test: JSON wrapped in ```json ... ``` fences → still parses correctly
- Test: JSON with missing required field → returns None
- Test: completely invalid string → returns None
- Test: confidence value > 1.0 → returns None (pydantic rejects it)
- Test: empty string → returns None

**5.8 Integration test `tests/integration/test_anomaly_to_llm.py`**
- Generate anomaly report from disk_failing simulator
- Call correlator.correlate()
- Assert: returns IncidentReport (not None)
- Assert: `hardware_involved == True` (SMART fault is hardware)
- Assert: `auto_remediable == False` (hardware faults never are)
- Assert: `confidence >= 0.0 and confidence <= 1.0`
- Assert: `len(causal_chain) >= 1`

**5.9 Design and iterate prompt**
- Run the integration test multiple times, inspect raw LLM output
- Iterate on system prompt wording until:
  - JSON is always valid
  - `hardware_involved` is correctly set for hardware vs software faults
  - Causal chain is ordered correctly
  - Confidence is appropriately calibrated (not always 0.99)
- This step takes iteration — budget 2–3 hours

**5.10 Verify Phase 5**
```bash
pytest tests/unit/test_prompt_builder.py tests/unit/test_response_parser.py -v
pytest tests/integration/test_anomaly_to_llm.py -v
# Check SQLite: sqlite3 data/incidents.db "SELECT root_cause, confidence FROM incidents LIMIT 5;"
```

---

## PHASE 6 — Remediation Engine
*Act safely or escalate clearly.*

**6.1 Create `remediation/gate_checker.py`**
- `evaluate(incident: IncidentReport, whitelist: dict)` → `ActionDecision | EscalationDecision`
- Gate 1: `incident.confidence >= threshold` → else return EscalationDecision(reason='low_confidence')
- Gate 2: `incident.suggested_action in whitelist` AND parameters pass regex validation → else EscalationDecision(reason='not_whitelisted')
- Gate 3: `incident.hardware_involved == False` → else EscalationDecision(reason='hardware_root_cause')
- All three pass → return ActionDecision(action_id, parameters, incident_id)

**6.2 Create `remediation/snapshot.py`**
- `take_snapshot(action_id, incident_id)` → captures pre-action state
- For `restart_service`: saves `systemctl show <unit>` output + last 100 journal lines
- For `vacuum_logs`: saves current disk usage stats
- For `reap_zombies`: saves process tree snapshot
- For `trigger_vacuum`: saves `pg_stat_user_tables` snapshot
- Saves to `data/snapshots/{incident_id}_{action_id}_{timestamp}/`

**6.3 Create `remediation/actions/restart_service.py`**
- `execute(unit_name: str)` → runs `sudo systemctl restart {unit_name}`
- Validates `unit_name` against regex before subprocess call
- Returns `(success: bool, output: str)`

**6.4 Create `remediation/actions/vacuum_logs.py`**
- `execute(max_size: str)` → runs `sudo journalctl --vacuum-size={max_size}`
- Validates `max_size` matches `^\d+[MG]$`
- Returns `(success, output)`

**6.5 Create `remediation/actions/reap_zombies.py`**
- `execute()` → finds all zombie PIDs via `/proc/<pid>/status`, signals their parents with `SIGCHLD`
- Pure Python, no subprocess needed for the reaping logic
- Returns `(success, zombies_reaped_count)`

**6.6 Create `remediation/actions/trigger_vacuum.py`**
- `execute(table_name: str)` → connects via psycopg2, runs `VACUUM ANALYZE {table_name}`
- Validates table_name against `^[a-z_]+$`
- Returns `(success, output)`

**6.7 Create `remediation/executor.py`**
- `execute(decision: ActionDecision)` → `ActionResult`
- Step 1: `snapshot.take_snapshot()`
- Step 2: Write audit_log 'action_starting' entry
- Step 3: Route to correct action handler based on `decision.action_id`
- Step 4: Call action handler, capture result
- Step 5: Wait 60 seconds, check if anomaly persisted (query InfluxDB for same metric)
- Step 6: Write audit_log 'action_complete' with success/fail and outcome
- Step 7: Update incident record with action_taken and action_outcome
- Return ActionResult

**6.8 Create `remediation/audit_logger.py`**
- `log_action_start(incident_id, action_id, parameters)` → INSERT audit_log
- `log_action_complete(incident_id, action_id, success, outcome)` → INSERT audit_log
- `log_escalation(incident_id, reason, human_report)` → INSERT audit_log + update incident
- `log_gate_failure(incident_id, gate_name, reason)` → INSERT audit_log
- All methods are synchronous, use the same SQLite connection

**6.9 Create `hardware_diagnostics/component_localizer.py`**
- Maps fault signals to physical components
- SMART fault on sda → "Primary storage drive (Drive Bay 1)"
- ECC fault → reads DIMM slot from rasdaemon logs or IPMI → "DIMM Slot A2"
- CPU thermal → reads IPMI sensor name → "CPU Socket 0"
- Returns `ComponentLocation(name, physical_location, slot_id)`

**6.10 Create `hardware_diagnostics/urgency_model.py`**
- Takes acceleration data from smart_acceleration or ecc_rate_model
- `compute_urgency(acceleration_result)` → `UrgencyLevel` (LOW / MEDIUM / HIGH / CRITICAL)
- HIGH: doubling faster than 12 hours
- CRITICAL: doubling faster than 4 hours OR any uncorrectable errors
- Returns estimated time-to-failure range in hours

**6.11 Create `hardware_diagnostics/vendor_lookup.py`**
- Loads `config/vendor_smart_tables.json`
- `lookup(drive_model_string)` → returns vendor-specific attribute names + known failure thresholds
- `suggest_replacement(drive_model_string, capacity_gb)` → returns suggested replacement description
- Fuzzy matches drive model strings (real drives have inconsistent model strings)

**6.12 Create `hardware_diagnostics/report_generator.py`**
- `generate(incident, component_location, urgency, vendor_info)` → plain-language string report
- Builds second LLM prompt: full component details, urgency, workload context, vendor SMART table
- Instructs LLM to produce a structured plain-language report for a non-specialist
- Output includes: what's happening, urgency, what to do step by step, data risk, replacement guidance
- Parses response — no strict schema needed here, just string output
- Saves to incident record as `human_report`

**6.13 Write unit tests `tests/unit/test_gate_checker.py`**
- Test: high confidence + whitelisted action + no hardware → ActionDecision returned
- Test: low confidence → EscalationDecision with reason='low_confidence'
- Test: hardware_involved=True → EscalationDecision with reason='hardware_root_cause'
- Test: action not in whitelist → EscalationDecision with reason='not_whitelisted'
- Test: parameter fails regex → EscalationDecision

**6.14 Write unit tests `tests/unit/test_executor.py`**
- Test: vacuum_logs action runs without error in test environment
- Test: reap_zombies finds and signals zombie (create a test zombie process first)
- Test: audit log written before and after action
- Test: snapshot directory created before action

**6.15 Integration test `tests/integration/test_llm_to_remediation.py`**
- Build a mock IncidentReport with `hardware_involved=False`, `confidence=0.9`, `suggested_action='vacuum_logs'`
- Run through gate_checker → executor
- Assert: audit_log has two entries (start + complete)
- Assert: snapshot directory exists
- Assert: incident record updated with action_taken

**6.16 Verify Phase 6**
```bash
pytest tests/unit/test_gate_checker.py tests/unit/test_executor.py -v
pytest tests/integration/test_llm_to_remediation.py -v
```

---

## PHASE 7 — Main Pipeline Loop
*Wire everything together.*

**7.1 Create `pipeline/main_loop.py`**

Full loop:
```
while True:
    snapshot = orchestrator.collect()
    influx_client.write(snapshot.readings)
    anomaly_report = aggregator.run(snapshot)

    if not anomaly_report.flagged_signals:
        sleep(POLL_INTERVAL)
        continue

    incident = correlator.correlate(anomaly_report, influx_client, system_context)

    if incident is None:
        audit_logger.log_escalation(None, 'parse_failure', str(anomaly_report))
        sleep(POLL_INTERVAL)
        continue

    decision = gate_checker.evaluate(incident, whitelist)

    if isinstance(decision, ActionDecision):
        result = executor.execute(decision)

    elif isinstance(decision, EscalationDecision):
        if incident.hardware_involved:
            location = component_localizer.locate(incident)
            urgency = urgency_model.compute_urgency(incident)
            vendor = vendor_lookup.lookup(incident.root_cause_component)
            report = report_generator.generate(incident, location, urgency, vendor)
        else:
            report = incident.plain_language_summary

        audit_logger.log_escalation(incident.id, decision.reason, report)

    sleep(POLL_INTERVAL)
```

**7.2 Add graceful shutdown**
- Handle `SIGTERM` and `SIGINT`
- Complete current loop iteration before exiting
- Log shutdown event to audit log

**7.3 Add startup checks**
- Verify InfluxDB is reachable
- Verify SQLite can be written to
- Verify Anthropic API key is valid (make one test call)
- Verify all collector modules load without error
- Print startup summary: mode (simulate/live), poll interval, confidence threshold

**7.4 End-to-end test `tests/e2e/test_full_pipeline.py`**
- Start pipeline with disk_failing_slow simulator
- Run for 30 poll intervals (use POLL_INTERVAL=1 second for test)
- Assert: at least one IncidentReport written to SQLite
- Assert: that incident has `hardware_involved=True`
- Assert: that incident has an escalation record in audit_log
- Assert: human_report is not empty

- Start pipeline with log_flood fault
- Run for 10 poll intervals
- Assert: IncidentReport with `fault_category='os'`
- Assert: ActionDecision leads to vacuum_logs action
- Assert: audit_log has 'action_complete' entry

**7.5 Verify Phase 7**
```bash
pytest tests/e2e/test_full_pipeline.py -v

# Live smoke test — run pipeline for 2 minutes, watch output
POLL_INTERVAL_SECONDS=5 python -m pipeline.main_loop
# Watch: should print "No anomalies detected" on healthy runs
```

---

## PHASE 8 — Fault Injection Suite
*The experimental apparatus.*

**8.1 Create `fault_injection/scenarios/disk_fill.py`**
- `inject(target_percent: float)`:
  - Calculates bytes needed to reach target_percent of /tmp
  - Runs `fallocate -l {bytes} /tmp/fault_fill_{uuid}`
  - Records file path for cleanup
- `cleanup()`: deletes the fallocate file
- `verify_injected()`: checks `shutil.disk_usage('/tmp').percent >= target_percent`

**8.2 Create `fault_injection/scenarios/memory_pressure.py`**
- `inject(percent_of_ram: float, duration_seconds: int)`:
  - Calculates bytes = total_ram * percent_of_ram
  - Runs `stress-ng --vm 1 --vm-bytes {bytes} --timeout {duration}` in background subprocess
  - Stores PID
- `cleanup()`: kills stress-ng PID
- `verify_injected()`: checks `/proc/meminfo` MemAvailable is reduced

**8.3 Create `fault_injection/scenarios/cpu_stress.py`**
- `inject(cores: int, duration_seconds: int)`:
  - Runs `stress-ng --cpu {cores} --timeout {duration}` in background
- `cleanup()`: kills process
- `verify_injected()`: checks `/proc/loadavg` 1-minute > threshold

**8.4 Create `fault_injection/scenarios/zombie_factory.py`**
- `inject(count: int)`:
  - Uses Python `multiprocessing` to spawn `count` child processes that immediately exit
  - Parent process does NOT call `wait()` — leaves them as zombies
- `cleanup()`: reaps all zombie PIDs
- `verify_injected()`: scans `/proc/*/status` for State: Z entries

**8.5 Create `fault_injection/scenarios/log_flood.py`**
- `inject(messages_per_second: int, duration_seconds: int)`:
  - Spawns background thread that calls `subprocess.run(['logger', '-t', 'fault_injection', msg])` rapidly
- `cleanup()`: stops the thread
- `verify_injected()`: checks journald error count for 'fault_injection' tag increased

**8.6 Create `fault_injection/scenarios/db_vacuum_starve.py`**
- `inject()`:
  - Connects to PostgreSQL
  - Creates a temp table and inserts + deletes rows rapidly → generates dead tuples
- `cleanup()`: drops the temp table, triggers manual VACUUM
- `verify_injected()`: checks `pg_stat_user_tables.n_dead_tup` above threshold

**8.7 Create `fault_injection/scenarios/nfs_hang_sim.py`**
- Since there's no NFS server in Codespaces, simulate via the simulator
- `inject()`: sets simulator flag that causes journald_collector to emit NFS timeout log lines
- `cleanup()`: clears the flag

**8.8 Define the 47 scenarios in `fault_injection/scenario_registry.py`**

| # | Fault Type | Severity | Expected Detection Method | Expected Outcome |
|---|---|---|---|---|
| 1–5 | Disk filling (50/60/70/80/90%) | Soft/Hard | Z-score on disk usage | Auto: vacuum_logs |
| 6–8 | SMART reallocating slow/med/fast | Hard | SMART acceleration | Escalate: hardware |
| 9–10 | ECC errors degrading | Hard | ECC rate model | Escalate: hardware |
| 11–13 | CPU thermal low/med/high | Hard | Z-score + IPMI | Escalate: hardware |
| 14–15 | Memory pressure 70/90% | Soft | Isolation Forest | Escalate: investigate |
| 16–18 | Zombie processes 5/20/50 | Soft | Z-score process count | Auto: reap_zombies |
| 19–21 | Log flood low/med/high | Soft | Z-score journald count | Auto: vacuum_logs |
| 22–24 | DB dead tuples low/med/high | Soft | Z-score pg_stat | Auto: trigger_vacuum |
| 25–27 | NFS hang (simulated) | Hard | Journald error pattern | Escalate: investigate |
| 28–30 | Service crash (simulated) | Soft | Journald restart events | Auto: restart_service |
| 31–33 | Combined: disk fill + zombie | Soft | Multiple detectors | Auto: both |
| 34–36 | Combined: SMART + DB bloat | Hard + Soft | Cross-layer | Escalate hardware, auto DB |
| 37–39 | Gradual CPU + memory over 2hrs | Soft | Seasonal baseline | Escalate: investigate |
| 40–42 | False alarm scenarios (no fault) | None | Should NOT flag | No action |
| 43–45 | Noise injection (random spikes) | None | Should NOT flag | No action |
| 46–47 | Simultaneous multi-fault | Mixed | Cross-layer correlation | Mixed |

**8.9 Create `fault_injection/scenario_runner.py`**
- `run_scenario(scenario_id, condition, repetition)`:
  - Reset system state (clear InfluxDB warm-up data, clear SQLite incidents)
  - Start the pipeline in a subprocess
  - Record `injection_time`
  - Wait up to `max_detection_wait_seconds` for an IncidentReport to appear in SQLite
  - Record `detection_time` → `MTTD = detection_time - injection_time`
  - Wait up to `max_resolution_wait_seconds` for audit_log 'action_complete' or 'escalation'
  - Record `resolution_time` → `MTTR = resolution_time - injection_time`
  - Record: TP/FP/FN (compare expected vs actual outcome)
  - Kill pipeline subprocess
  - Run `cleanup()` on the scenario
  - Return `ScenarioResult`

- `run_all(condition: str, output_csv: str)`:
  - Loops all 47 scenarios × 5 repetitions
  - Writes results to CSV after each run (never lose progress)
  - Prints progress: `Scenario 12/47, Rep 3/5, MTTD: 94s`

**8.10 Verify Phase 8**
```bash
# Test each scenario class individually
python -c "
from fault_injection.scenarios.disk_fill import DiskFillScenario
s = DiskFillScenario()
s.inject(target_percent=0.7)
print('Injected:', s.verify_injected())
s.cleanup()
print('Cleaned:', not s.verify_injected())
"

# Run one scenario through scenario_runner
python -m fault_injection.scenario_runner --scenario 1 --condition our_system --reps 1
```

---

## PHASE 9 — Evaluation
*Produce the numbers that go in the paper.*

**9.1 Create `evaluation/metrics_recorder.py`**
- `load_results(csv_path)` → returns DataFrame
- `compute_precision(df)` → TP / (TP + FP)
- `compute_recall(df)` → TP / (TP + FN)
- `compute_f1(precision, recall)` → 2 * P * R / (P + R)
- `compute_mttd_stats(df)` → mean, median, std, 95th percentile
- `compute_mttr_stats(df)` → same
- `summary_table(df)` → per-scenario-category breakdown

**9.2 Create `evaluation/baseline_runner.py`**
- `no_automation` condition: pipeline runs but with `AUTO_REMEDIATE=False` and no LLM — just logs raw anomalies. Human resolution time is fixed at 900 seconds (15 minutes) for software faults, 3600 seconds (1 hour) for hardware — conservative values from literature.
- `rule_based` condition: replace LLM correlator with simple threshold rules → fixed scripted responses. Restart service if `journald_errors > 10`. Vacuum if `disk_percent > 85`. No causal reasoning, no gates.

**9.3 Run all three conditions**
```bash
# This will take several hours total — run in order
python -m fault_injection.scenario_runner \
  --condition no_automation \
  --output data/results/no_automation.csv

python -m fault_injection.scenario_runner \
  --condition rule_based \
  --output data/results/rule_based.csv

python -m fault_injection.scenario_runner \
  --condition our_system \
  --output data/results/our_system.csv
```

**9.4 Create `evaluation/wilcoxon_test.py`**
- Load all three result CSVs
- For MTTD: Wilcoxon(our_system, no_automation), Wilcoxon(our_system, rule_based)
- For MTTR: same
- For precision, recall, F1: report raw values per condition
- Output: stats table with W, p-value, effect size per comparison
- Print: "Result is statistically significant at p < 0.05" or "Not significant"

**9.5 Create `evaluation/results_plotter.py`**
- Box plot: MTTD distribution per condition
- Box plot: MTTR distribution per condition
- Bar chart: Precision / Recall / F1 per condition
- Line plot: per-scenario-category MTTD heatmap
- Save all as PNG to `docs/figures/`

**9.6 Create `notebooks/04_results_analysis.ipynb`**
- Load results, run wilcoxon_test, generate all plots
- Annotate each figure with interpretation
- This notebook becomes the source for the paper's results section

**9.7 Verify Phase 9**
```bash
python -m evaluation.wilcoxon_test \
  --our data/results/our_system.csv \
  --baseline_no_auto data/results/no_automation.csv \
  --baseline_rule data/results/rule_based.csv

python -m evaluation.results_plotter \
  --results data/results/ \
  --output docs/figures/
```

---

## PHASE 10 — Paper Writeup Support
*Turn your code into a publication.*

**10.1 Document the prompt design**
- Create `docs/prompt_design.md`
- Full system prompt text
- Full example user message with annotated sections
- Rationale for each design decision (why JSON schema in system prompt, why include recent history)

**10.2 Document the fault taxonomy**
- Create `docs/fault_taxonomy.md`
- All 47 scenarios organized by category
- For each: fault description, injection method, detection method, expected outcome
- This becomes Table 1 in your paper

**10.3 Document the architecture**
- Create `docs/architecture.md`
- Reference the system architecture slide from your PPT
- Describe each layer and its interface contracts
- Document the MODE switching design

**10.4 Compute and record final numbers**
From the evaluation results, extract and record:
- Mean MTTD: our system vs baselines (with % improvement)
- Mean MTTR: our system vs baselines (with % improvement)
- Precision, Recall, F1 for each condition
- False positive rate (key safety metric)
- Causal chain accuracy (manually verify 20 randomly sampled incidents — did the chain make sense?)
- Wilcoxon p-values and effect sizes

**10.5 Write paper sections in order**
1. Abstract (write last)
2. Introduction — problem, existing gap, our contribution
3. Related Work — cite all 8 papers from literature review
4. System Design — architecture, each layer, design decisions
5. Experimental Setup — Codespaces environment, simulator methodology, Backblaze calibration, 47 scenarios
6. Results — tables + figures from evaluation
7. Discussion — what the numbers mean, limitations, threats to validity
8. Conclusion + Future Work
9. Abstract (now write it)

---

## PHASE 11 — Final Cleanup

**11.1 Code quality**
```bash
black .                          # format everything
pytest tests/ --cov=. --cov-report=html   # full test suite with coverage
# Target: > 80% coverage on core modules
```

**11.2 README.md**
- Project overview
- Setup instructions (clone → Codespaces → pip install → .env → run)
- How to run in simulate mode
- How to run the full evaluation
- How to interpret the audit log

**11.3 Final repository commit**
- All code committed
- `data/backblaze/` gitignored (too large)
- `data/snapshots/` gitignored
- `data/results/` committed (small CSVs — evidence for paper)
- `.env` gitignored, `.env.example` committed

---

## Summary Timeline

| Phase | Content | Estimated Time |
|---|---|---|
| 0 | Environment | 0.5 days |
| 1 | Simulator + Backblaze calibration | 2 days |
| 2 | Collector layer | 2 days |
| 3 | Storage layer | 1 day |
| 4 | Anomaly detection | 3 days |
| 5 | LLM reasoning + prompt iteration | 4 days |
| 6 | Remediation engine | 3 days |
| 7 | Main pipeline + E2E test | 2 days |
| 8 | Fault injection suite | 3 days |
| 9 | Evaluation runs + stats | 3 days |
| 10 | Paper writeup | 2 weeks |
| 11 | Cleanup + submission prep | 2 days |
| **Total** | | **~10 weeks** |