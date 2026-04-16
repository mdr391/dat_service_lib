"""
In-Memory Repository Adapter — For Testing.

"""
import statistics as stats_module
from datetime import datetime
from typing import List, Optional, Dict

from ...core.ports.interfaces import ReadingRepository, ThresholdRepository
from ...core.domain.models import (
    SensorReading, SensorStats, SensorThreshold,
)


class InMemoryReadingRepo(ReadingRepository):
    """
    In-memory implementation of ReadingRepository.
    Used for unit tests and local development.
    """

    def __init__(self) -> None:
        self._readings: List[SensorReading] = []

    def save(self, reading: SensorReading) -> None:
        self._readings.append(reading)

    def save_batch(self, readings: List[SensorReading]) -> int:
        self._readings.extend(readings)
        return len(readings)

    def get_by_sensor(
        self,
        sensor_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[SensorReading]:
        results = [r for r in self._readings if r.sensor_id == sensor_id]
        if start:
            results = [r for r in results if r.timestamp >= start]
        if end:
            results = [r for r in results if r.timestamp <= end]
        results.sort(key=lambda r: r.timestamp, reverse=True)
        return results[:limit]

    def get_latest(self, sensor_id: str) -> Optional[SensorReading]:
        readings = self.get_by_sensor(sensor_id, limit=1)
        return readings[0] if readings else None

    def get_stats(
        self,
        sensor_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> Optional[SensorStats]:
        readings = self.get_by_sensor(sensor_id, start=start, end=end, limit=10000)
        if not readings:
            return None

        values = [r.value for r in readings]
        anomaly_count = sum(
            1 for r in readings if r.status.value == "anomaly"
        )

        return SensorStats(
            sensor_id=sensor_id,
            count=len(values),
            mean=stats_module.mean(values),
            std_dev=stats_module.stdev(values) if len(values) > 1 else 0.0,
            min_value=min(values),
            max_value=max(values),
            anomaly_count=anomaly_count,
            period_start=min(r.timestamp for r in readings),
            period_end=max(r.timestamp for r in readings),
        )

    def clear(self) -> None:
        """Test helper — clear all data."""
        self._readings.clear()

    def __len__(self) -> int:
        return len(self._readings)


class InMemoryThresholdRepo(ThresholdRepository):
    """In-memory threshold configuration store."""

    def __init__(self) -> None:
        self._thresholds: Dict[str, SensorThreshold] = {}

    def get_threshold(self, sensor_id: str) -> Optional[SensorThreshold]:
        return self._thresholds.get(sensor_id)

    def save_threshold(self, threshold: SensorThreshold) -> None:
        self._thresholds[threshold.sensor_id] = threshold

    def get_all_thresholds(self) -> List[SensorThreshold]:
        return list(self._thresholds.values())
