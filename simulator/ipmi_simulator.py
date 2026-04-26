"""
Generates realistic IPMI sensor readings.
"""
import yaml
import numpy as np
from datetime import datetime


class IpmiSimulator:
    def __init__(self, fault_profile="healthy_baseline"):
        self.fault_profile = fault_profile
        self.time_step = 0
        self.profile_config = self._load_profile()
        self.sensors = self._init_sensors()

    def _load_profile(self):
        profile_path = f"simulator/fault_profiles/{self.fault_profile}.yaml"
        try:
            with open(profile_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            return {"name": "healthy_baseline", "ipmi": {"fault_mode": "healthy"}}

    def _init_sensors(self):
        return {
            "CPU_Temp": {"value": 45, "unit": "degrees C", "status": "ok"},
            "Fan1": {"value": 2400, "unit": "RPM", "status": "ok"},
            "Fan2": {"value": 2380, "unit": "RPM", "status": "ok"},
            "Volt_12V": {"value": 12.10, "unit": "Volts", "status": "ok"},
            "Volt_5V": {"value": 5.05, "unit": "Volts", "status": "ok"},
            "PS1_Status": {"value": "Presence detected", "unit": "", "status": "ok"}
        }

    def get_reading(self):
        self.time_step += 1
        fault_mode = self.profile_config.get("ipmi", {}).get("fault_mode", "healthy")
        
        if fault_mode == "cpu_thermal":
            # CPU temp escalates
            self.sensors["CPU_Temp"]["value"] = min(95, 45 + self.time_step * 2)
            if self.sensors["CPU_Temp"]["value"] > 85:
                self.sensors["CPU_Temp"]["status"] = "nc"  # non-critical
        elif fault_mode == "fan_failure":
            # Fan RPM drops
            self.sensors["Fan1"]["value"] = max(0, 2400 - self.time_step * 100)
            if self.sensors["Fan1"]["value"] < 500:
                self.sensors["Fan1"]["status"] = "cr"  # critical
        elif fault_mode == "psu_unstable":
            # Voltage ripple
            self.sensors["Volt_12V"]["value"] = 12.0 + np.random.normal(0, 0.4)
            if abs(self.sensors["Volt_12V"]["value"] - 12.0) > 0.6:
                self.sensors["Volt_12V"]["status"] = "nc"
        else:
            # Healthy - small random variations
            self.sensors["CPU_Temp"]["value"] = 45 + np.random.normal(0, 2)
            self.sensors["Fan1"]["value"] = 2400 + np.random.normal(0, 50)
            self.sensors["Fan2"]["value"] = 2380 + np.random.normal(0, 50)
        
        return {
            "sensors": [
                {"name": k, **v} for k, v in self.sensors.items()
            ],
            "timestamp": datetime.utcnow().isoformat()
        }