"""
Generates realistic SMART telemetry streams.
Simulates drive health degradation based on fault profiles.
"""
import yaml
import numpy as np
from datetime import datetime
from simulator.backblaze_loader import BackblazeLoader


class SmartSimulator:
    def __init__(self, fault_profile="healthy_baseline", drive_model="WDC_WD40EFRX"):
        self.fault_profile = fault_profile
        self.drive_model = drive_model
        self.loader = BackblazeLoader()
        self.time_step = 0  # in hours
        self.attributes = self._init_attributes()
        self.profile_config = self._load_profile()

    def _load_profile(self):
        """Load fault profile YAML."""
        profile_path = f"simulator/fault_profiles/{self.fault_profile}.yaml"
        try:
            with open(profile_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            # Return healthy defaults if profile not found
            return {
                "name": "healthy_baseline",
                "smart": {"fault_mode": "healthy"}
            }

    def _init_attributes(self):
        """Initialize SMART attributes at healthy baseline."""
        return {
            "reallocated_sector_ct": 0,
            "reported_uncorrectable_errors": 0,
            "current_pending_sector_ct": 0,
            "offline_uncorrectable": 0,
            "command_timeout": 0,
            "read_error_rate": 0,
            "seek_error_rate": 0,
            "power_on_hours": 8760,  # 1 year
            "power_cycle_count": 365,
            "temperature_celsius": 35
        }

    def get_reading(self):
        """Generate a SMART reading for current time step."""
        self.time_step += 1
        
        # Update attributes based on fault mode
        fault_mode = self.profile_config.get("smart", {}).get("fault_mode", "healthy")
        
        if fault_mode == "reallocating":
            self._apply_degradation("reallocated_sector_ct")
        elif fault_mode == "pending":
            self._apply_degradation("current_pending_sector_ct")
        elif fault_mode == "uncorrectable":
            self._apply_degradation("reported_uncorrectable_errors")
        
        # Add normal increments for counters
        self.attributes["power_on_hours"] += 1
        
        # Small temperature variation
        self.attributes["temperature_celsius"] = 35 + np.random.normal(0, 2)
        
        # Build smartctl-like output
        return {
            "device": {
                "name": f"/dev/sda",
                "type": "sat",
                "model_name": self.drive_model
            },
            "smart_attributes": {
                "reallocated_sector_ct": {
                    "id": 5,
                    "raw_value": int(self.attributes["reallocated_sector_ct"]),
                    "value": max(0, 100 - int(self.attributes["reallocated_sector_ct"]))
                },
                "reported_uncorrectable_errors": {
                    "id": 187,
                    "raw_value": int(self.attributes["reported_uncorrectable_errors"]),
                    "value": 100
                },
                "current_pending_sector_ct": {
                    "id": 197,
                    "raw_value": int(self.attributes["current_pending_sector_ct"]),
                    "value": max(0, 100 - int(self.attributes["current_pending_sector_ct"]))
                },
                "offline_uncorrectable": {
                    "id": 198,
                    "raw_value": int(self.attributes["offline_uncorrectable"]),
                    "value": 100
                },
                "command_timeout": {
                    "id": 188,
                    "raw_value": int(self.attributes["command_timeout"]),
                    "value": 100
                },
                "temperature_celsius": {
                    "id": 194,
                    "raw_value": int(self.attributes["temperature_celsius"]),
                    "value": int(self.attributes["temperature_celsius"])
                },
                "power_on_hours": {
                    "id": 9,
                    "raw_value": int(self.attributes["power_on_hours"]),
                    "value": 100
                }
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    def _apply_degradation(self, attribute_name):
        """Apply exponential degradation curve to an attribute."""
        params = self.loader.get_failure_curve(attribute_name)
        
        # Exponential growth: value = baseline + A * exp(k * t) + noise
        t_days = self.time_step / 24.0
        deterministic = params["baseline"] + params["A"] * np.exp(params["k"] * t_days)
        noise = np.random.normal(0, params["noise_std"])
        
        self.attributes[attribute_name] = max(0, deterministic + noise)