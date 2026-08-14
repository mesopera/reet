"""
Vendor-specific SMART attribute interpretation and replacement guidance.
"""
import json
from dataclasses import dataclass


@dataclass
class VendorInfo:
    vendor: str
    attribute_name: str
    failure_threshold: int
    suggested_replacement: str


REPLACEMENT_SUGGESTIONS = {
    "WDC":     "WD Red Plus (NAS-rated) or WD Black (performance) — match original capacity",
    "Seagate": "Seagate IronWolf (NAS-rated) or Seagate Barracuda — match original capacity",
    "Samsung": "Samsung 870 EVO or 990 PRO (SSD) — match original capacity and interface",
    "Toshiba": "Toshiba N300 (NAS-rated) or P300 — match original capacity",
}


class VendorLookup:
    def __init__(self, table_path="config/vendor_smart_tables.json"):
        with open(table_path) as f:
            self.table = json.load(f)

    def lookup(self, drive_model: str, attribute_id: str) -> VendorInfo:
        model_upper = drive_model.upper()
        for vendor, data in self.table.items():
            for prefix in data.get("prefix", []):
                if prefix.upper() in model_upper:
                    attr = data.get("attributes", {}).get(str(attribute_id))
                    if attr:
                        return VendorInfo(
                            vendor=vendor,
                            attribute_name=attr["name"],
                            failure_threshold=attr["failure_threshold"],
                            suggested_replacement=REPLACEMENT_SUGGESTIONS.get(vendor, "Consult vendor documentation")
                        )
        return VendorInfo(
            vendor="Unknown",
            attribute_name=f"Attribute {attribute_id}",
            failure_threshold=50,
            suggested_replacement="Vendor not recognised — consult drive documentation"
        )