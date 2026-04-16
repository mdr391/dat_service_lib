"""
Domain Models — Pure Python, Zero Infrastructure Dependencies.

"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any


# ═══════════════════════════════════════════════════════════════
# Enums — constrain values at the domain level
# ═══════════════════════════════════════════════════════════════

class SensorUnit(Enum):
    """Valid sensor measurement units."""
    FAHRENHEIT = "fahrenheit"
    CELSIUS = "celsius"
    VOLTS = "volts"
    PSI = "psi"
    PERCENT = "percent"
    MM_PER_SEC = "mm/s"


class ReadingStatus(Enum):
    """Processing status of a sensor reading."""
    PENDING = "pending"
    VALID = "valid"
    ANOMALY = "anomaly"
    INVALID = "invalid"


class OrderStatus(Enum):
    """Production order lifecycle status."""
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETE = "complete"
    FAILED = "failed"


# ═══════════════════════════════════════════════════════════════
# Domain Models — Dataclasses
# ═══════════════════════════════════════════════════════════════

@dataclass
class SensorReading:
    """
    A single reading from a factory sensor.
    """
    sensor_id: str
    value: float
    unit: SensorUnit
    timestamp: datetime = field(default_factory=datetime.utcnow)
    status: ReadingStatus = ReadingStatus.PENDING
    correlation_id: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_anomaly(self, threshold_low: float, threshold_high: float) -> bool:
        """Pure business logic — no infrastructure dependency."""
        return self.value < threshold_low or self.value > threshold_high

    def mark_as_anomaly(self) -> "SensorReading":
        """Returns a new reading marked as anomaly (immutable pattern)."""
        return SensorReading(
            sensor_id=self.sensor_id,
            value=self.value,
            unit=self.unit,
            timestamp=self.timestamp,
            status=ReadingStatus.ANOMALY,
            correlation_id=self.correlation_id,
            tags=self.tags + ["anomaly"],
            metadata=self.metadata,
        )

    def mark_as_valid(self) -> "SensorReading":
        """Returns a new reading marked as valid."""
        return SensorReading(
            sensor_id=self.sensor_id,
            value=self.value,
            unit=self.unit,
            timestamp=self.timestamp,
            status=ReadingStatus.VALID,
            correlation_id=self.correlation_id,
            tags=self.tags,
            metadata=self.metadata,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for JSON/logging."""
        d = asdict(self)
        d["unit"] = self.unit.value
        d["status"] = self.status.value
        d["timestamp"] = self.timestamp.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SensorReading":
        """Deserialize from dict."""
        data = data.copy()
        data["unit"] = SensorUnit(data["unit"])
        data["status"] = ReadingStatus(data["status"])
        if isinstance(data["timestamp"], str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


@dataclass(frozen=True)
class SensorThreshold:
    """
    Immutable threshold configuration for a sensor.
    frozen=True means it can't be modified after creation — safe to share.
    """
    sensor_id: str
    min_value: float
    max_value: float
    unit: SensorUnit

    def is_within_range(self, value: float) -> bool:
        return self.min_value <= value <= self.max_value


@dataclass
class SensorStats:
    """Aggregated statistics for a sensor over a time period."""
    sensor_id: str
    count: int
    mean: float
    std_dev: float
    min_value: float
    max_value: float
    anomaly_count: int = 0
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


@dataclass
class ProcessingResult:
    """Result of processing a batch of readings."""
    total_processed: int
    valid_count: int
    anomaly_count: int
    invalid_count: int
    errors: List[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total_processed == 0:
            return 0.0
        return (self.valid_count + self.anomaly_count) / self.total_processed
