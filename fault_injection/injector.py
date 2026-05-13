"""
Simple injector interface — wraps scenario classes.
"""
from fault_injection.scenario_runner import get_scenario_instance, SCENARIO_REGISTRY


def get_scenario(scenario_id: str):
    entry = next((s for s in SCENARIO_REGISTRY if s['id'] == scenario_id), None)
    if entry is None:
        raise ValueError(f"Scenario {scenario_id} not found")
    return get_scenario_instance(entry)