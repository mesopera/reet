"""
Append-only audit trail for all remediation events.
"""
from datetime import datetime
from storage.incident_store import IncidentStore


class AuditLogger:
    def __init__(self):
        self.store = IncidentStore()

    def log_gate_result(self, incident_id: str, gate: str, passed: bool, reason: str):
        self.store.save_audit_event(
            incident_id,
            f"gate_{'passed' if passed else 'failed'}",
            f"gate={gate} reason={reason}"
        )

    def log_action_start(self, incident_id: str, action_id: str, parameters: dict):
        self.store.save_audit_event(
            incident_id,
            'action_starting',
            f"action={action_id} params={parameters}"
        )

    def log_action_complete(self, incident_id: str, action_id: str, success: bool, output: str):
        self.store.save_audit_event(
            incident_id,
            'action_complete',
            f"action={action_id} success={success} output={output[:200]}"
        )

    def log_escalation(self, incident_id: str, reason: str, human_report: str):
        self.store.save_audit_event(
            incident_id,
            'escalation',
            f"reason={reason}"
        )
        if incident_id:
            self.store.update_incident(incident_id, {
                'escalated': 1,
                'human_report': human_report
            })