"""
Executes whitelisted remediation actions safely.
"""
import time
from dataclasses import dataclass
from remediation.gate_checker import ActionDecision
from remediation.snapshot import SnapshotManager
from remediation.audit_logger import AuditLogger
from storage.incident_store import IncidentStore


@dataclass
class ActionResult:
    incident_id: str
    action_id: str
    success: bool
    output: str
    snapshot_path: str


class Executor:
    def __init__(self):
        self.snapshot = SnapshotManager()
        self.audit = AuditLogger()
        self.store = IncidentStore()

    def execute(self, decision: ActionDecision) -> ActionResult:
        # Take pre-action snapshot
        snapshot_path = self.snapshot.take(decision.incident_id, decision.action_id)

        # Log start
        self.audit.log_action_start(
            decision.incident_id,
            decision.action_id,
            decision.parameters
        )

        # Route to correct action handler
        success, output = self._dispatch(decision)

        # Log completion
        self.audit.log_action_complete(
            decision.incident_id,
            decision.action_id,
            success,
            output
        )

        # Update incident record
        self.store.update_incident(decision.incident_id, {
            'action_taken': decision.action_id,
            'action_outcome': 'success' if success else 'failed'
        })

        return ActionResult(
            incident_id=decision.incident_id,
            action_id=decision.action_id,
            success=success,
            output=output,
            snapshot_path=snapshot_path
        )

    def _dispatch(self, decision: ActionDecision) -> tuple[bool, str]:
        action_id = decision.action_id
        params = decision.parameters

        if action_id == 'vacuum_logs':
            from remediation.actions.vacuum_logs import execute
            return execute(params.get('max_size', '500M'))

        elif action_id == 'reap_zombies':
            from remediation.actions.reap_zombies import execute
            return execute()

        elif action_id == 'restart_service':
            from remediation.actions.restart_service import execute
            return execute(params.get('unit_name', ''))

        elif action_id == 'trigger_vacuum':
            from remediation.actions.trigger_vacuum import execute
            return execute(params.get('table_name', 'public'))

        else:
            return False, f"Unknown action: {action_id}"