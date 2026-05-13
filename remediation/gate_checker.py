"""
Three safety gates before any autonomous action.
All three must pass — any failure routes to human escalation.
"""
import re
import yaml
from dataclasses import dataclass
from reasoning.schemas import IncidentReport


@dataclass
class ActionDecision:
    action_id: str
    parameters: dict
    incident_id: str
    reason: str


@dataclass
class EscalationDecision:
    reason: str
    gate_failed: str
    incident: IncidentReport


def load_whitelist(path='config/whitelist.yaml') -> dict:
    with open(path, 'r') as f:
        return yaml.safe_load(f)


class GateChecker:
    def __init__(self, confidence_threshold=0.75, whitelist_path='config/whitelist.yaml'):
        self.confidence_threshold = confidence_threshold
        self.whitelist = load_whitelist(whitelist_path)

    def evaluate(self, incident: IncidentReport, incident_id: str):
        # Gate 1 — Confidence
        if incident.confidence < self.confidence_threshold:
            return EscalationDecision(
                reason=f"Confidence {incident.confidence} below threshold {self.confidence_threshold}",
                gate_failed='confidence',
                incident=incident
            )

        # Gate 2 — Hardware safety
        if incident.hardware_involved:
            return EscalationDecision(
                reason="Hardware fault in causal chain — never auto-remediate",
                gate_failed='hardware',
                incident=incident
            )

        # Gate 3 — Whitelist
        if not incident.auto_remediable or not incident.suggested_action:
            return EscalationDecision(
                reason="Incident marked not auto-remediable or no action suggested",
                gate_failed='whitelist',
                incident=incident
            )

        action_id = incident.suggested_action
        whitelist_entry = self._find_action(action_id)

        if whitelist_entry is None:
            return EscalationDecision(
                reason=f"Action '{action_id}' not found in whitelist",
                gate_failed='whitelist',
                incident=incident
            )

        # Validate fault category allowed
        allowed_categories = whitelist_entry.get('fault_categories', [])
        if incident.fault_category not in allowed_categories:
            return EscalationDecision(
                reason=f"Fault category '{incident.fault_category}' not allowed for action '{action_id}'",
                gate_failed='whitelist',
                incident=incident
            )

        # Build and validate parameters
        params = self._build_params(incident, whitelist_entry)
        if params is None:
            return EscalationDecision(
                reason=f"Parameter validation failed for action '{action_id}'",
                gate_failed='whitelist',
                incident=incident
            )

        return ActionDecision(
            action_id=action_id,
            parameters=params,
            incident_id=incident_id,
            reason=f"All gates passed — executing {action_id}"
        )

    def _find_action(self, action_id: str) -> dict | None:
        for action in self.whitelist.get('actions', []):
            if action['id'] == action_id:
                return action
        return None

    def _build_params(self, incident: IncidentReport, whitelist_entry: dict) -> dict | None:
        params = {}
        for param_def in whitelist_entry.get('parameters', []):
            name = param_def['name']
            pattern = param_def.get('pattern')

            # Set sensible defaults based on action type
            if name == 'max_size':
                params[name] = '500M'
            elif name == 'unit_name':
                # Extract from root cause component
                component = incident.root_cause_component
                if not component.endswith('.service'):
                    component = f"{component}.service"
                params[name] = component
            elif name == 'table_name':
                params[name] = 'public'
            else:
                params[name] = ''

            # Validate against regex
            if pattern and params[name]:
                if not re.match(pattern, params[name]):
                    print(f"Parameter {name}='{params[name]}' failed pattern {pattern}")
                    return None

        return params