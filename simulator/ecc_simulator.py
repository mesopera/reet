"""
Generates realistic ECC error counts.
"""
import yaml
import numpy as np
from datetime import datetime


class EccSimulator:
    def __init__(self, fault_profile="healthy_baseline"):
        self.fault_profile = fault_profile
        self.time_step = 0
        self.ce_count = 0
        self.ue_count = 0
        self.profile_config = self._load_profile()

    def _load_profile(self):
        profile_path = f"simulator/fault_profiles/{self.fault_profile}.yaml"
        try:
            with open(profile_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            return {"name": "healthy_baseline", "ecc": {"fault_mode": "healthy"}}

    def get_reading(self):
        self.time_step += 1
        fault_mode = self.profile_config.get("ecc", {}).get("fault_mode", "healthy")
        
        if fault_mode == "degrading":
            # Exponential growth in correctable errors
            t_hours = self.time_step
            self.ce_count = int(2 * np.exp(0.08 * t_hours) + np.random.poisson(1))
        else:
            # Healthy - occasional random single-bit flips
            self.ce_count += np.random.poisson(0.1)
        
        # Uncorrectable errors are rare
        if fault_mode == "critical":
            self.ue_count += np.random.poisson(0.01)
        
        return {
            "ce_count": int(self.ce_count),
            "ue_count": int(self.ue_count),
            "timestamp": datetime.utcnow().isoformat()
        }