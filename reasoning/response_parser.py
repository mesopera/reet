"""
Parses and validates LLM JSON output.
"""
import json
import re
from reasoning.schemas import IncidentReport


class ResponseParser:
    def parse(self, raw_response: str) -> IncidentReport | None:
        if not raw_response:
            return None

        # Strip markdown code fences if present
        cleaned = raw_response.strip()
        cleaned = re.sub(r'^```json\s*', '', cleaned)
        cleaned = re.sub(r'^```\s*', '', cleaned)
        cleaned = re.sub(r'\s*```$', '', cleaned)
        cleaned = cleaned.strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as e:
            print(f"JSON parse failed: {e}")
            print(f"Raw response was: {raw_response[:200]}")
            return None

        try:
            incident = IncidentReport.model_validate(parsed)
            return incident
        except Exception as e:
            print(f"Schema validation failed: {e}")
            return None