"""
Base class for all telemetry collectors.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class TelemetryReading:
    source: str           # 'smart', 'ipmi', 'ecc', 'proc', etc.
    component: str        # 'sda', 'cpu0', 'dimm_a2', etc.
    metric: str           # 'reallocated_sector_ct', 'cpu_temp', etc.
    value: float
    unit: str
    timestamp: datetime
    raw: dict             # full original reading


class BaseCollector(ABC):
    @abstractmethod
    def collect(self) -> list[TelemetryReading]:
        """Return list of readings from this source."""
        pass