"""
SQLite store for incidents and audit log.
"""
import json
import os
import sqlite3
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


class IncidentStore:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.getenv('SQLITE_PATH', 'data/incidents.db')
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        schema_path = 'storage/schema.sql'
        with open(schema_path, 'r') as f:
            schema = f.read()
        with self._conn() as conn:
            conn.executescript(schema)

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def save_incident(self, incident: dict) -> None:
        sql = '''
        INSERT OR REPLACE INTO incidents
        (id, detected_at, root_cause, confidence, causal_chain,
         fault_category, hardware_involved, action_taken, action_outcome,
         escalated, human_report, reasoning_chain, resolved_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        with self._conn() as conn:
            conn.execute(sql, (
                incident['id'],
                incident.get('detected_at', datetime.utcnow().isoformat()),
                incident['root_cause'],
                incident['confidence'],
                json.dumps(incident.get('causal_chain', [])),
                incident['fault_category'],
                int(incident.get('hardware_involved', False)),
                incident.get('action_taken'),
                incident.get('action_outcome'),
                int(incident.get('escalated', False)),
                incident.get('human_report'),
                incident.get('reasoning_chain', ''),
                incident.get('resolved_at')
            ))

    def save_audit_event(self, incident_id: str, event_type: str, detail: str) -> None:
        sql = '''
        INSERT INTO audit_log (incident_id, timestamp, event_type, detail)
        VALUES (?, ?, ?, ?)
        '''
        with self._conn() as conn:
            conn.execute(sql, (
                incident_id,
                datetime.utcnow().isoformat(),
                event_type,
                detail
            ))

    def get_incident(self, incident_id: str) -> dict | None:
        sql = 'SELECT * FROM incidents WHERE id = ?'
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(sql, (incident_id,)).fetchone()
            if row:
                d = dict(row)
                d['causal_chain'] = json.loads(d['causal_chain'])
                return d
            return None

    def list_incidents(self, limit: int = 50) -> list:
        sql = 'SELECT * FROM incidents ORDER BY detected_at DESC LIMIT ?'
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, (limit,)).fetchall()
            return [dict(r) for r in rows]

    def update_incident(self, incident_id: str, updates: dict) -> None:
        fields = ', '.join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [incident_id]
        sql = f'UPDATE incidents SET {fields} WHERE id = ?'
        with self._conn() as conn:
            conn.execute(sql, values)