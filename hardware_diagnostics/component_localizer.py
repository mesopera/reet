"""
Maps a hardware fault signal to a physical component location.
"""
from dataclasses import dataclass


@dataclass
class ComponentLocation:
    name: str
    physical_location: str
    slot_id: str


COMPONENT_MAP = {
    ("smart", "sda"):        ComponentLocation("Primary storage drive", "Drive Bay 1", "sda"),
    ("smart", "sdb"):        ComponentLocation("Secondary storage drive", "Drive Bay 2", "sdb"),
    ("ecc", "memory"):       ComponentLocation("System memory", "DIMM Slot A2", "dimm_a2"),
    ("ipmi", "cpu_temp"):    ComponentLocation("CPU", "CPU Socket 0", "cpu0"),
    ("ipmi", "fan1"):        ComponentLocation("Chassis fan 1", "Fan Header 1", "fan1"),
    ("ipmi", "fan2"):        ComponentLocation("Chassis fan 2", "Fan Header 2", "fan2"),
    ("ipmi", "volt_12v"):    ComponentLocation("Power supply — 12V rail", "PSU Bay", "psu1"),
    ("ipmi", "volt_5v"):     ComponentLocation("Power supply — 5V rail", "PSU Bay", "psu1"),
}


def locate(source: str, component: str) -> ComponentLocation:
    key = (source, component)
    if key in COMPONENT_MAP:
        return COMPONENT_MAP[key]
    return ComponentLocation(
        name=f"{source}/{component}",
        physical_location="Unknown — not in component map",
        slot_id=component
    )