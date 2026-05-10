CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY,
    detected_at TEXT NOT NULL,
    root_cause TEXT NOT NULL,
    confidence REAL NOT NULL,
    causal_chain TEXT NOT NULL,
    fault_category TEXT NOT NULL,
    hardware_involved INTEGER NOT NULL,
    action_taken TEXT,
    action_outcome TEXT,
    escalated INTEGER NOT NULL DEFAULT 0,
    human_report TEXT,
    reasoning_chain TEXT NOT NULL,
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id TEXT,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    detail TEXT NOT NULL
);