"""
Loads Backblaze dataset and extracts calibration parameters for SMART simulation.
"""
import json
import os
from pathlib import Path


class BackblazeLoader:
    def __init__(self, calibration_path="data/backblaze/calibration_params.json"):
        self.calibration_path = calibration_path
        self.params = self._load_or_create_default()

    def _load_or_create_default(self):
        """Load calibration params or create defaults if file doesn't exist."""
        if os.path.exists(self.calibration_path):
            with open(self.calibration_path, 'r') as f:
                return json.load(f)
        else:
            # Default parameters based on literature and Backblaze patterns
            # These are placeholder values - will be replaced when real dataset is analyzed
            default = {
                "reallocated_sector_ct": {
                    "baseline": 0,
                    "A": 2.0,  # initial amplitude
                    "k": 0.15,  # growth rate (per day)
                    "noise_std": 0.3
                },
                "reported_uncorrectable_errors": {
                    "baseline": 0,
                    "A": 1.0,
                    "k": 0.2,
                    "noise_std": 0.2
                },
                "current_pending_sector_ct": {
                    "baseline": 0,
                    "A": 1.5,
                    "k": 0.18,
                    "noise_std": 0.25
                },
                "offline_uncorrectable": {
                    "baseline": 0,
                    "A": 1.0,
                    "k": 0.12,
                    "noise_std": 0.15
                },
                "command_timeout": {
                    "baseline": 0,
                    "A": 10.0,
                    "k": 0.1,
                    "noise_std": 2.0
                }
            }
            return default

    def get_failure_curve(self, attribute_name):
        """Get calibration params for a specific SMART attribute."""
        if attribute_name in self.params:
            return self.params[attribute_name]
        else:
            # Return safe defaults for unknown attributes
            return {
                "baseline": 0,
                "A": 1.0,
                "k": 0.1,
                "noise_std": 0.2
            }