"""
Orchestrates the full reasoning step.
anomalies -> prompt -> LLM -> parse -> IncidentReport
"""
import uuid
from datetime import datetime
from anomaly.anomaly_aggregator import AnomalyReport
from reasoning.prompt_builder import build_system_prompt, build_user_message
from reasoning.llm_client import LLMClient
from reasoning.response_parser import ResponseParser
from storage.incident_store import IncidentStore


class Correlator:
    def __init__(self):
        self.llm = LLMClient()
        self.parser = ResponseParser()
        self.store = IncidentStore()
        self.system_prompt = build_system_prompt()

    def correlate(self, anomaly_report: AnomalyReport, system_context: dict = None):
        user_message = build_user_message(anomaly_report, system_context)

        # Call LLM
        raw_response = self.llm.call(self.system_prompt, user_message)

        if raw_response is None:
            self.store.save_audit_event(
                None, 'llm_call_failed',
                f"LLM returned None for run_id={anomaly_report.run_id}"
            )
            return None

        # Parse response
        incident = self.parser.parse(raw_response)

        if incident is None:
            self.store.save_audit_event(
                None, 'parse_failed',
                f"Failed to parse LLM response: {raw_response[:300]}"
            )
            return None

        # Save to SQLite
        incident_id = str(uuid.uuid4())
        self.store.save_incident({
            'id': incident_id,
            'detected_at': datetime.utcnow().isoformat(),
            'root_cause': incident.root_cause,
            'confidence': incident.confidence,
            'causal_chain': [s.model_dump() for s in incident.causal_chain],
            'fault_category': incident.fault_category,
            'hardware_involved': incident.hardware_involved,
            'reasoning_chain': incident.reasoning,
            'escalated': False
        })

        self.store.save_audit_event(
            incident_id, 'incident_created',
            f"confidence={incident.confidence}, category={incident.fault_category}"
        )

        return incident