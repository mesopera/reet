"""
Runs all detectors and returns a unified AnomalyReport.
"""
from dataclasses import dataclass, field
from datetime import datetime
from collector.base_collector import TelemetryReading
from anomaly.zscore_detector import ZScoreDetector
from anomaly.isolation_forest import IsolationForestDetector
from anomaly.smart_acceleration import SmartAccelerationDetector, MONITORED_ATTRIBUTES
from anomaly.ecc_rate_model import EccRateDetector


@dataclass
class FlaggedSignal:
    source: str
    component: str
    metric: str
    value: float
    anomaly_type: str
    severity: float       # 0.0 - 1.0
    details: dict


@dataclass
class AnomalyReport:
    run_id: str
    timestamp: datetime
    flagged_signals: list[FlaggedSignal]
    total_readings_scanned: int


class AnomalyAggregator:
    def __init__(self):
        self.zscore = ZScoreDetector()
        self.iso_forest = IsolationForestDetector()
        self.smart_accel = SmartAccelerationDetector()
        self.ecc_rate = EccRateDetector()

    def run(self, snapshot) -> AnomalyReport:
        flagged = []
        readings = snapshot.readings

        for reading in readings:
            # Update detectors with new reading
            self.zscore.update(reading)
            if reading.source == 'smart':
                self.smart_accel.update(reading)
            if reading.source == 'ecc':
                self.ecc_rate.update(reading)

        # Update isolation forest with full snapshot
        self.iso_forest.update(readings)

        # Z-score check on each reading
        for reading in readings:
            z = self.zscore.score(reading)
            if z and z > self.zscore.threshold:
                severity = min(1.0, z / 10.0)
                flagged.append(FlaggedSignal(
                    source=reading.source,
                    component=reading.component,
                    metric=reading.metric,
                    value=reading.value,
                    anomaly_type='zscore_spike',
                    severity=severity,
                    details={'zscore': round(z, 3)}
                ))

        # Isolation Forest check
        if self.iso_forest.is_anomalous(readings):
            score = self.iso_forest.score(readings)
            flagged.append(FlaggedSignal(
                source='system',
                component='all',
                metric='multivariate',
                value=score or 0.0,
                anomaly_type='isolation_forest',
                severity=0.7,
                details={'if_score': round(score, 3) if score else 0}
            ))

        # SMART acceleration check
        accel_results = self.smart_accel.run_all()
        for result in accel_results:
            flagged.append(FlaggedSignal(
                source='smart',
                component=result.component,
                metric=result.attribute,
                value=result.current_value,
                anomaly_type='smart_acceleration',
                severity=result.urgency_score,
                details={
                    'first_derivative': round(result.first_derivative, 4),
                    'second_derivative': round(result.second_derivative, 4)
                }
            ))

        # ECC rate check
        ecc_result = self.ecc_rate.compute()
        if ecc_result and ecc_result.is_accelerating:
            flagged.append(FlaggedSignal(
                source='ecc',
                component='memory',
                metric='ce_count',
                value=ecc_result.current_rate_per_hour,
                anomaly_type='ecc_rate_acceleration',
                severity=ecc_result.urgency_score,
                details={
                    'rate_per_hour': round(ecc_result.current_rate_per_hour, 3),
                    'doubling_time_hours': ecc_result.doubling_time_hours
                }
            ))

        return AnomalyReport(
            run_id=snapshot.run_id,
            timestamp=snapshot.timestamp,
            flagged_signals=flagged,
            total_readings_scanned=len(readings)
        )