"""
Generates the plain-language hardware repair report.
Combines urgency, location, and vendor data into an LLM-authored report,
with a deterministic fallback if the LLM call fails.
"""
from datetime import datetime
from hardware_diagnostics.component_localizer import locate
from hardware_diagnostics.urgency_model import assess, UrgencyTier
from hardware_diagnostics.vendor_lookup import VendorLookup
from reasoning.llm_client import LLMClient


def generate(incident, flagged_signal, drive_model="WDC WD40EFRX-68N32N0") -> str:
    """
    incident: IncidentReport from the reasoning layer
    flagged_signal: the FlaggedSignal that triggered this (has source, component, details)
    """
    location = locate(flagged_signal.source, flagged_signal.component)

    doubling_time = flagged_signal.details.get("doubling_time_hours")
    has_uncorrectable = "uncorrectable" in incident.root_cause.lower()
    urgency = assess(doubling_time, has_uncorrectable, flagged_signal.value)

    vendor_lookup = VendorLookup()
    attribute_id = "5" if "reallocated" in incident.root_cause.lower() else "187"
    vendor = vendor_lookup.lookup(drive_model, attribute_id)

    # Try LLM-generated plain-language report; fall back to deterministic template
    llm_report = _try_llm_report(incident, location, urgency, vendor)
    if llm_report:
        return llm_report

    return _template_report(incident, location, urgency, vendor)


def _try_llm_report(incident, location, urgency, vendor) -> str | None:
    try:
        client = LLMClient()
        prompt = f"""Write a plain-language hardware repair report for a non-specialist IT operator.
Root cause: {incident.root_cause}
Component: {location.name} ({location.physical_location})
Urgency: {urgency.tier.value} — {urgency.rationale}
Vendor: {vendor.vendor}, suggested part: {vendor.suggested_replacement}

Write 4-6 short sentences covering: what is happening, how urgent it is, what to check first,
and what to order. No jargon. No SMART attribute numbers."""
        response = client.call("You write short, clear hardware repair guidance for non-experts.", prompt)
        return response
    except Exception:
        return None


def _template_report(incident, location, urgency, vendor) -> str:
    return f"""HARDWARE REPAIR REPORT — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
{'='*60}
COMPONENT:    {location.name}
LOCATION:     {location.physical_location}
URGENCY:      {urgency.tier.value}
VENDOR:       {vendor.vendor}

WHAT IS HAPPENING:
{incident.plain_language_summary}

WHY THIS URGENCY LEVEL:
{urgency.rationale}
{f"Estimated time to failure: {urgency.estimated_hours_to_failure:.0f} hours" if urgency.estimated_hours_to_failure else ""}

WHAT TO DO:
  1. Back up any critical data from this component immediately.
  2. {"Replace within 24 hours — do not delay" if urgency.tier == urgency.tier.CRITICAL else "Schedule replacement during next maintenance window"}
  3. Order replacement part: {vendor.suggested_replacement}
  4. Do not restart dependent services until hardware is confirmed healthy.
{'='*60}"""