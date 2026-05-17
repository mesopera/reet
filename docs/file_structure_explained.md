# What i have actually built, file by file

### .devcontainer/devcontainer.json
Tells GitHub Codespaces what environment to spin up. Uses Python 3.11 base image and runs `pip install -r requirements.txt` automatically when the container starts. Without this the Codespace boots into a generic environment and you'd have to set everything up manually every time.

### requirements.txt
Lists every Python package the project depends on. `pip install -r requirements.txt` installs all of them in one shot. Needed because Python doesn't ship with any of our ML, API, or storage libraries — they all have to be installed explicitly.

### .env / .env.example
`.env` holds your actual secrets — Groq API key, InfluxDB token, mode switch. Never committed to git. `.env.example` is the template with placeholder values that is committed, so anyone cloning the repo knows what variables to set. The `python-dotenv` library loads `.env` into `os.environ` at startup so every module can read these values with `os.getenv()`.

### config/settings.yaml
Central configuration for all tunable parameters — poll interval, confidence threshold, Z-score window sizes, Isolation Forest contamination factor, SMART acceleration sensitivity, LLM model name. Kept separate from code so you can adjust thresholds without touching Python files. Read by modules using PyYAML.

### config/whitelist.yaml
Defines exactly which actions the system is allowed to take autonomously, which fault categories permit each action, and what parameter formats are valid. This file is the hard boundary of the system's authority — the gate checker reads it and nothing outside this list can ever be executed. Kept in a config file rather than hardcoded so operators can review and modify it without reading source code.

### config/vendor_smart_tables.json
Maps drive manufacturer prefixes (WDC, ST, MZ, TOSHIBA) to vendor-specific SMART attribute interpretations and failure thresholds. SMART attribute meanings are not universal — Samsung uses attribute 177 for wear leveling, WD uses it for something different. Without this table the system would misinterpret vendor-specific attributes. JSON because it's flat lookup data with no logic, easy to extend for new vendors.

### simulator/backblaze_loader.py
Loads calibration parameters (amplitude A, growth rate k, noise standard deviation) for each SMART attribute from a JSON file. If the calibration file doesn't exist yet it returns sensible defaults so the simulator still works before the Backblaze dataset has been analysed. These parameters determine the shape of the degradation curves the simulator generates.

### simulator/smart_simulator.py
The most important simulator file. Generates SMART attribute readings that look like real `smartctl --json` output. In healthy mode it returns stable values with small random noise. In fault mode (reallocating, pending, uncorrectable) it applies the exponential curve `value = A * exp(k * t) + noise` calibrated from real Backblaze drive failures. This is what the smart_collector reads in simulate mode — the rest of the system never knows the data isn't real.

### simulator/ipmi_simulator.py
Same concept for IPMI sensor data. Generates CPU temperature, fan RPM, voltage rail, and PSU readings in the same format that real `ipmitool sdr list` produces. In fault mode (cpu_thermal, fan_failure, psu_unstable) values escalate realistically. The ipmi_collector reads this in simulate mode.

### simulator/ecc_simulator.py
Generates ECC correctable error counts. Healthy mode produces occasional Poisson-distributed single-bit flips (realistic — real DRAM flips bits occasionally). Degrading mode applies exponential growth to ce_count, simulating a failing DIMM accumulating errors faster over time. The ecc_collector reads this in simulate mode.

### simulator/fault_profiles/*.yaml
Each YAML file describes one fault scenario — which fault mode to use for each simulator (SMART, IPMI, ECC), how aggressive the degradation is, and what the expected detection window should be. `healthy_baseline.yaml` keeps everything normal. `disk_failing_slow.yaml` sets SMART to reallocating mode with moderate acceleration. `disk_failing_fast.yaml` uses aggressive acceleration. The simulators load their assigned profile at instantiation.

### collector/base_collector.py
Defines two things: the `TelemetryReading` dataclass (the universal unit of telemetry — source, component, metric, value, unit, timestamp, raw dict) and the `BaseCollector` abstract class with a `collect()` method every collector must implement. This exists so the orchestrator can treat all eight collectors identically without knowing what each one does internally.

### collector/hardware/smart_collector.py
Implements `BaseCollector` for SMART data. Checks the `MODE` env var — if simulate, calls `SmartSimulator.get_reading()` and converts the output dict into a list of `TelemetryReading` objects (one per SMART attribute). If live, it would run `smartctl -x --json /dev/sda`. The conversion from simulator/smartctl output to `TelemetryReading` objects is the key work — it normalises heterogeneous source data into a single uniform type everything downstream can use.

### collector/hardware/ipmi_collector.py
Same pattern for IPMI. Simulate mode calls `IpmiSimulator.get_reading()`, live mode would call `ipmitool`. Filters out non-numeric sensors (PSU presence strings etc.) since anomaly detectors only operate on numeric values.

### collector/hardware/ecc_collector.py
Same pattern for ECC errors. Simulate mode calls `EccSimulator.get_reading()`, live mode reads `/sys/devices/system/edac/mc0/ce_count` directly. Returns two readings per call — one for correctable errors (ce_count) and one for uncorrectable (ue_count).

### collector/os_layer/proc_collector.py
Reads real `/proc` files — not simulated. `/proc/meminfo` for memory availability, `/proc/loadavg` for CPU load, `/proc/stat` for CPU percentages, `/proc/vmstat` for paging activity. These are real OS metrics from whatever system is running. This is why even in simulate mode we get authentic load and memory signal — the OS telemetry is always live.

### collector/os_layer/sys_collector.py
Reads real `/sys` filesystem. `/sys/block/sda/stat` for disk I/O counters, `/sys/class/net/eth0/statistics/` for NIC error and drop counts. Same principle as proc_collector — always real, no simulation needed.

### collector/os_layer/disk_collector.py
Uses Python's `shutil.disk_usage()` and `os.statvfs()` to report filesystem usage percentage and inode usage per mount point. This is what detects the disk_fill fault injection scenarios — fallocate fills the filesystem and this collector sees the usage spike.

### collector/services/journald_collector.py
Runs `journalctl --since "5 minutes ago" --output=json` via subprocess and counts error and warning log lines per systemd unit. In a Codespace without journald it degrades gracefully. This is the signal source for log_flood and nfs_hang scenarios.

### collector/services/process_collector.py
Reads `/proc/<pid>/status` for all running processes. Counts processes per state, specifically looking for `State: Z` (zombie). This is what detects the zombie_factory fault injection — zombie processes accumulate and this collector sees the count increase.

### collector/database/postgres_collector.py
Connects via psycopg2 and queries `pg_stat_activity`, `pg_stat_bgwriter`, and `pg_stat_user_tables`. If PostgreSQL is not installed or not running it catches the exception and returns an empty list silently. This is the signal source for the db_vacuum_starve scenario — dead tuple counts in `pg_stat_user_tables` grow as the bloat accumulates.

### collector/orchestrator.py
The entry point for the entire collection layer. Instantiates all eight collectors, runs all their `collect()` methods simultaneously using `ThreadPoolExecutor`, assigns a shared `run_id` and `timestamp` to every reading in the cycle, and returns a `CollectionSnapshot`. The parallel execution matters — if collectors ran sequentially, readings from different sources would have different timestamps and cross-layer temporal ordering would be unreliable.

### storage/influx_client.py
Wraps the official `influxdb-client` library. `write()` converts `TelemetryReading` objects into InfluxDB line protocol points and writes them with retry logic. `query_range()` fetches a time window of a specific metric as a pandas DataFrame — used by the SMART acceleration detector to pull 72 hours of history. `query_latest()` returns the most recent value of a metric — used for post-action persistence checks. InfluxDB specifically because it's purpose-built for time-series — range queries over millions of timestamped rows are much faster than in SQLite or PostgreSQL.

### storage/schema.sql
Defines two SQLite tables. `incidents` stores every detected incident — root cause, confidence, causal chain (as JSON), fault category, hardware involvement, action taken, escalation status, human report. `audit_log` stores every event in the system's decision-making process — gate checks, action starts, action completions, escalations — linked to their parent incident by ID. Kept in a separate SQL file rather than inline strings so it's readable and version-controllable.

### storage/incident_store.py
SQLite CRUD wrapper. On init it creates the database file and runs schema.sql. `save_incident()` inserts a new incident record. `save_audit_event()` appends an audit log entry. `get_incident()` retrieves by ID. `update_incident()` updates specific fields (used to add action_taken and action_outcome after remediation). SQLite specifically because it requires no server, no configuration, and produces a single file that can be inspected directly with any SQLite browser.

### anomaly/zscore_detector.py
Maintains a rolling deque of recent values per (component, metric) pair. `update()` adds a new reading. `score()` returns the Z-score (number of standard deviations from the rolling mean). `is_anomalous()` returns true if the score exceeds the threshold. Requires a minimum of 10 readings before scoring — prevents false positives during startup when the window is too small to compute meaningful statistics. This catches sudden spikes in any individual metric.

### anomaly/isolation_forest.py
Wraps scikit-learn's `IsolationForest`. Collects the first 200 collection snapshots as training data. After warm-up, fits a model and scores every new snapshot as a multivariate feature vector. Re-trains every 1000 readings. Returns an anomaly score — more negative means more anomalous (sklearn convention). This catches unusual combinations of metrics where no single metric is extreme — the Isolation Forest sees the whole picture at once.

### anomaly/seasonal_baseline.py
Uses statsmodels STL decomposition to separate a metric's time-series into trend, seasonal (daily cycle), and residual components. The residual is what the system actually tests for anomalies. This prevents the Z-score detector from firing every morning when CPU load naturally rises with business hours — those increases are expected and subtracted out. Queries InfluxDB for 7 days of history to establish the seasonal pattern.

### anomaly/smart_acceleration.py
The novel component. For each monitored SMART attribute, pulls 72 hours of history from the in-memory buffer, computes `numpy.gradient()` twice (first derivative = rate of change, second derivative = acceleration), and flags if the second derivative is positive and significant. A positive second derivative means the attribute is not just increasing but increasing faster over time — the signature of exponential degradation. The urgency score is the product of acceleration magnitude and current value — fast-accelerating high-value attributes are most urgent.

### anomaly/ecc_rate_model.py
Same derivative approach for ECC correctable error counts. Splits the 24-hour history window in half and compares the error rate in the second half to the first half. If the rate in the second half is more than 1.5× the first half the memory is flagged as accelerating. Estimates doubling time — how many hours until the error rate doubles again — which feeds into urgency assessment.

### anomaly/anomaly_aggregator.py
The single entry point for the entire anomaly detection layer. Takes a `CollectionSnapshot`, runs all four detectors, collects every flag each detector raises, and assembles them into an `AnomalyReport` containing a list of `FlaggedSignal` objects. Each `FlaggedSignal` has source, component, metric, value, anomaly type, severity (0--1), and detector-specific details. If `flagged_signals` is empty the pipeline skips LLM reasoning entirely for that cycle.

### reasoning/schemas.py
Pydantic model definitions for the LLM's output. `CausalStep` has timestamp_offset, component, event, and caused_by. `IncidentReport` has root_cause, root_cause_component, confidence, fault_category, hardware_involved, causal_chain, auto_remediable, suggested_action, plain_language_summary, and reasoning. Validators enforce that confidence is 0--1, fault_category is one of the five allowed values, and suggested_action is one of the four whitelisted actions or null. Pydantic rejects any output that doesn't conform — this is the hard safety barrier.

### reasoning/prompt_builder.py
Constructs the two parts of every LLM call. The system prompt defines the LLM's role, outputs the full JSON schema it must follow, and states the rules (never infer hardware fault without sensor evidence, suggested_action must be from the allowed list, etc.). The user message assembles the server context (hostname, OS, uptime, services) and the flagged signals as a formatted JSON block. The prompt is templated not free-form — consistent structure means consistent output.

### reasoning/llm_client.py
Thin wrapper around the Groq client. Sends the system prompt and user message, receives the response text, handles rate limit errors with exponential backoff and retries. Returns the raw string. Designed so swapping from Groq to Ollama or Anthropic requires changing only this file — the interface (system_prompt in, raw_response out) stays the same.

### reasoning/response_parser.py
Takes the raw LLM string, strips markdown code fences if present (LLMs often wrap JSON in ```json blocks), runs `json.loads()`, then `IncidentReport.model_validate()`. Any exception at any step returns None — never raises. Returning None triggers escalation in the correlator. Logs the raw response and error on failure for debugging.

### reasoning/correlator.py
Orchestrates the full reasoning step. Receives an `AnomalyReport`, calls `prompt_builder` to construct the prompt, calls `llm_client` to get a response, calls `response_parser` to validate it, saves the result to SQLite, and returns the `IncidentReport`. This is the only place in the system where all three reasoning components are wired together.

### remediation/gate_checker.py
Implements the three-gate safety model. Takes an `IncidentReport` and evaluates: (1) confidence ≥ threshold, (2) suggested_action is on the whitelist and parameters pass regex validation, (3) hardware_involved is False. Returns either an `ActionDecision` (all gates passed) or an `EscalationDecision` (with the name of the failing gate and reason). This is the only place where the system decides to act — nothing else in the codebase makes that call.

### remediation/snapshot.py
Before any action executes, this captures the current state — disk usage, process count, load average — to a JSON file in `data/snapshots/{incident_id}_{action_id}_{timestamp}/`. This is the rollback reference. If an action makes things worse, the snapshot shows exactly what the system state was before the action ran.

### remediation/audit_logger.py
Thin wrapper around `IncidentStore.save_audit_event()` with named methods for each event type: `log_gate_result`, `log_action_start`, `log_action_complete`, `log_escalation`. Every event the system produces goes through here. The audit log is append-only by SQLite semantics — no UPDATE or DELETE on audit records.

### remediation/executor.py
Takes an `ActionDecision`, calls `snapshot.take()`, writes an audit start event, dispatches to the correct action handler via a simple if-elif chain, writes an audit complete event with success/fail, updates the incident record, and returns an `ActionResult`. The dispatch is explicit and finite — there is no dynamic import or eval, only named function calls to the four action modules.

### remediation/actions/restart_service.py
Runs `sudo systemctl restart {unit_name}` via subprocess. The unit_name has already been validated against the regex `^[a-z0-9_.-]+\.service$` by the gate checker before this is ever called. Returns (success bool, output string).

### remediation/actions/vacuum_logs.py
Runs `sudo journalctl --vacuum-size={max_size}` via subprocess. max_size validated as `^\d+[MG]$` before this is called. Returns (success bool, output string).

### remediation/actions/reap_zombies.py
Pure Python — no subprocess. Scans `/proc/*/status` for `State: Z`, reads the PPid field from each zombie's status file, sends SIGCHLD to that parent PID. SIGCHLD tells the parent that a child has changed state, prompting it to call wait() and reap the zombie. Returns (success bool, count of zombies found).

### remediation/actions/trigger_vacuum.py
Connects via psycopg2 and runs `VACUUM ANALYZE` with autocommit=True (VACUUM cannot run inside a transaction block). Skips gracefully if PostgreSQL is not available. Returns (success bool, output string).

### remediation/actions/remount_nfs.py
Stub file. NFS remounting is handled via simulation in the NFS hang scenario — there is no real NFS server in the Codespace environment to remount.

### hardware_diagnostics/component_localizer.py
Takes a hardware fault signal and maps it to a human-readable physical location. SMART fault on sda → "Primary storage drive (Drive Bay 1)". ECC fault → reads DIMM slot from EDAC sysfs or IPMI SEL → "DIMM Slot A2". Returns a `ComponentLocation` with name, physical_location, and slot_id.

### hardware_diagnostics/urgency_model.py
Takes the acceleration results from `smart_acceleration.py` or `ecc_rate_model.py` and classifies into four tiers: Monitor, Schedule Maintenance, High Urgency, Critical. High is triggered if the doubling time is under 12 hours. Critical if under 4 hours or any uncorrectable errors are present. Returns a `UrgencyLevel` enum and estimated time-to-failure range.

### hardware_diagnostics/vendor_lookup.py
Loads `config/vendor_smart_tables.json` and fuzzy-matches a drive model string (real drive model strings are inconsistent — "WDC WD40EFRX-68N32N0" needs to match the "WDC" prefix entry). Returns vendor-specific attribute names, failure thresholds, and a suggested replacement description.

### hardware_diagnostics/report_generator.py
Builds a second LLM prompt specifically for hardware faults, providing full component details, urgency tier, workload context, and vendor SMART information. The LLM produces plain-language repair instructions — what's happening, how urgent, what to do first, what data is at risk, what part to order. No strict schema on this output — it's human-facing text, not machine-parsed.

### fault_injection/scenarios/disk_fill.py
Uses `fallocate -l {bytes} /tmp/fault_fill_{uuid}` to pre-allocate a large file, driving disk usage to the target percentage. `verify_injected()` checks `shutil.disk_usage()`. `cleanup()` deletes the fallocate file. fallocate is used instead of `dd` because it allocates space without writing data — nearly instantaneous and doesn't stress the disk.

### fault_injection/scenarios/memory_pressure.py
Runs `stress-ng --vm 1 --vm-bytes {bytes} --timeout {duration}` as a background subprocess. `verify_injected()` checks `psutil.virtual_memory().percent`. `cleanup()` terminates the stress-ng process. stress-ng is used because it's purpose-built for this — it allocates and actively reads/writes the memory to prevent the OS from swapping it out.

### fault_injection/scenarios/cpu_stress.py
Runs `stress-ng --cpu {cores} --timeout {duration}` as a background subprocess. `verify_injected()` reads `/proc/loadavg` and checks that load exceeds cores × 0.5.

### fault_injection/scenarios/zombie_factory.py
Uses Python `os.fork()` to create child processes that immediately call `os._exit(0)` without the parent ever calling `wait()`. The exited children remain as zombies in the process table. The parent process is kept alive in a `multiprocessing.Process` so the zombies persist until `cleanup()` terminates it.

### fault_injection/scenarios/log_flood.py
Runs `logger -t fault_injection "ERROR: ..."` in a background thread at the configured rate. `logger` writes directly to journald. `verify_injected()` checks that the thread is still alive (journalctl not available in Codespaces so no log count check).

### fault_injection/scenarios/nfs_hang_sim.py
Runs `logger -t kernel "nfs: server not responding, timed out"` every 2 seconds in a background thread. This simulates what the kernel would log during a real NFS hang. The journald_collector picks up these log entries as NFS-related kernel errors.

### fault_injection/scenarios/db_vacuum_starve.py
Connects via psycopg2, creates a temporary table, inserts 1000 rows, then deletes them all without running VACUUM. This leaves 1000 dead tuples in `pg_stat_user_tables.n_dead_tup` — the signal that the db_vacuum_starve scenario produces. Skips gracefully if PostgreSQL is not available.

### fault_injection/scenario_runner.py
The experimental harness. For each scenario and repetition: injects the fault, starts running collection/detection/reasoning cycles, waits for either an IncidentReport to appear in SQLite (recording MTTD) or the maximum wait time to expire, records the result, cleans up, and writes to the output CSV. For no_automation and rule_based conditions it applies fixed representative MTTD/MTTR values rather than running the pipeline.

### fault_injection/injector.py
Simple lookup wrapper — given a scenario ID string like "S01", returns the corresponding instantiated scenario class. Used by other parts of the system that need to inject a specific scenario by ID without importing every scenario module directly.

### evaluation/metrics_recorder.py
Loads a results CSV and computes precision, recall, F1, and MTTD/MTTR statistics (mean, median, std, 95th percentile). Used both interactively in notebooks and programmatically by the wilcoxon test.

### evaluation/baseline_runner.py
Runs the no_automation and rule_based conditions through `scenario_runner.run_all()`. These conditions don't actually execute the pipeline — they apply fixed representative times to each scenario based on literature values for human response latency and threshold-based tool detection times.

### evaluation/wilcoxon_test.py
Loads all three result CSVs, aligns the MTTD and MTTR series, and runs `scipy.stats.wilcoxon()` with `alternative='greater'` (testing that baseline values are greater than our system values). Reports W statistic, p-value, rank-biserial effect size, and the percentage improvement. Also prints detection rates per condition.

### evaluation/results_plotter.py
Generates three matplotlib figures in the dark navy theme matching the presentation: MTTD box plot, MTTR box plot, and Precision/Recall/F1 grouped bar chart. Saves as PNG to `docs/figures/` for inclusion in the paper.

### pipeline/main_loop.py
The master control loop that wires everything together. On startup: runs checks for InfluxDB, SQLite, and API key. Then loops indefinitely: collect → write to InfluxDB → detect anomalies → if none, sleep; if anomalies, call LLM → evaluate gates → execute or escalate → log everything → sleep. Handles SIGTERM and SIGINT gracefully by completing the current cycle before shutting down.

### tests/unit/
One test file per module. Each tests the module in isolation — smart_simulator tests check that fault profiles produce increasing values, gate_checker tests verify each gate fires correctly, response_parser tests cover valid JSON, fenced JSON, missing fields, and invalid confidence values. These run fast and catch regressions when any module changes.

### tests/integration/
Tests that two or more modules work correctly together. `test_collect_to_anomaly.py` runs the orchestrator then the aggregator and checks that healthy data produces no flags and fault data eventually produces flags. `test_anomaly_to_llm.py` runs a disk_failing simulator through to correlator and checks the IncidentReport is valid. `test_llm_to_remediation.py` feeds a mock IncidentReport through gate_checker and executor.

### tests/e2e/test_full_pipeline.py
Runs the entire pipeline for N cycles with a specific fault profile injected and verifies that an incident appears in SQLite, the incident has the expected hardware_involved value, and the audit_log has the expected entries. This is the proof that all nine layers work together end to end.

### notebooks/
Four Jupyter notebooks used for analysis and tuning — not part of the running system. `01_backblaze_exploration.ipynb` explores the Backblaze dataset and identifies which SMART attributes are most predictive. `02_smart_acceleration_model.ipynb` fits exponential curves to pre-failure trajectories and extracts the A and k parameters that calibrate the simulator. `03_isolation_forest_tuning.ipynb` sweeps contamination parameter values and plots precision/recall to select the best value. `04_results_analysis.ipynb` loads the three result CSVs and generates all paper figures interactively.