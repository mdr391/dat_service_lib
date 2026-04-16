"""
Ports — Abstract interfaces that define what the domain NEEDS.


CRITICAL RULE: Ports live in core/, adapters live in adapters/.
The domain imports ports, NEVER adapters.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Dict, Any, Protocol

from ..domain.models import (
    SensorReading, SensorStats, SensorThreshold, ProcessingResult,
)


# ═══════════════════════════════════════════════════════════════
# OUTBOUND PORTS — What the domain needs from infrastructure
# ═══════════════════════════════════════════════════════════════

class ReadingRepository(ABC):
    """
    Port: Persistence for sensor readings.
    The domain calls these methods; adapters implement them.

    Implementations: PostgresReadingRepo, InMemoryReadingRepo
    """

    @abstractmethod
    def save(self, reading: SensorReading) -> None:
        """Persist a single reading."""
        ...

    @abstractmethod
    def save_batch(self, readings: List[SensorReading]) -> int:
        """Persist multiple readings. Returns count saved."""
        ...

    @abstractmethod
    def get_by_sensor(
        self,
        sensor_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[SensorReading]:
        """Query readings for a sensor within a time range."""
        ...

    @abstractmethod
    def get_latest(self, sensor_id: str) -> Optional[SensorReading]:
        """Get the most recent reading for a sensor."""
        ...

    @abstractmethod
    def get_stats(
        self,
        sensor_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> Optional[SensorStats]:
        """Compute aggregate statistics for a sensor."""
        ...


class ThresholdRepository(ABC):
    """Port: Persistence for sensor threshold configurations."""

    @abstractmethod
    def get_threshold(self, sensor_id: str) -> Optional[SensorThreshold]:
        """Get the threshold config for a sensor."""
        ...

    @abstractmethod
    def save_threshold(self, threshold: SensorThreshold) -> None:
        """Save or update a threshold configuration."""
        ...

    @abstractmethod
    def get_all_thresholds(self) -> List[SensorThreshold]:
        """Get all configured thresholds."""
        ...


class AlertNotifier(ABC):
    """
    Port: Send alerts when anomalies are detected.
    Implementations: SlackNotifier, EmailNotifier, LogNotifier
    """

    @abstractmethod
    def send_alert(
        self,
        sensor_id: str,
        message: str,
        severity: str = "warning",
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Send an alert. Returns True if delivered successfully."""
        ...


class MetricsEmitter(ABC):
    """
    Port: Emit metrics for observability.
    Implementation: PrometheusMetrics
    """

    @abstractmethod
    def increment_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> None:
        """Increment a counter metric."""
        ...

    @abstractmethod
    def observe_histogram(self, name: str, value: float,
                          labels: Optional[Dict[str, str]] = None) -> None:
        """Record a histogram observation (e.g., latency)."""
        ...

    @abstractmethod
    def set_gauge(self, name: str, value: float,
                  labels: Optional[Dict[str, str]] = None) -> None:
        """Set a gauge metric value."""
        ...


# ═══════════════════════════════════════════════════════════════
# STRATEGY PORT — Swappable algorithms (Strategy Pattern)
# ═══════════════════════════════════════════════════════════════

class AnomalyDetector(Protocol):
    """
    Strategy interface for anomaly detection algorithms.
    Uses Protocol (Python 3.8) for structural subtyping — any object
    with a matching .detect() method satisfies this contract.

    """
    def detect(self, values: List[float]) -> List[int]:
        """
        Detect anomalies in a list of values.
        Returns indices of anomalous values.
        """
        ...


# ═══════════════════════════════════════════════════════════════
# HEALTH CHECK PORT — Every service reports health
# ═══════════════════════════════════════════════════════════════

class HealthCheck(ABC):
    """
    Port: Health check for service dependencies.
    K8s liveness/readiness probes call these.
    """

    @abstractmethod
    def check(self) -> Dict[str, Any]:
        """
        Returns health status.
        {"status": "healthy", "details": {...}} or
        {"status": "unhealthy", "error": "..."}
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the dependency being checked."""
        ...
