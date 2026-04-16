"""
DAT Service Library — Shared service infrastructure using Hexagonal Architecture.

USAGE:
    from dat_service_lib import (
        SensorReading, SensorService, ServiceConfig,
        setup_logging, InMemoryReadingRepo,
    )
"""
from .core.domain.models import (
    SensorReading, SensorUnit, SensorStats, SensorThreshold,
    ReadingStatus, ProcessingResult, OrderStatus,
)
from .core.domain.exceptions import (
    DATServiceError, SensorError, SensorNotFoundError,
    ReadingOutOfRangeError, InvalidReadingError, RepositoryError, CircuitOpenError,
)
from .core.domain.validators import (
    validate_sensor_id, validate_reading_value, validate_reading, is_statistical_anomaly,
)
from .core.ports.interfaces import (
    ReadingRepository, ThresholdRepository, AlertNotifier, MetricsEmitter, AnomalyDetector, HealthCheck,
)
from .core.services.sensor_service import SensorService
from .adapters.persistence.in_memory_repo import InMemoryReadingRepo, InMemoryThresholdRepo
from .adapters.messaging.alert_adapters import LogAlertNotifier, SlackAlertNotifier, CompositeAlertNotifier
from .adapters.observability.logging import setup_logging, generate_correlation_id, PrometheusMetrics, NoOpMetrics
from .adapters.config.settings import ServiceConfig
from .utils.resilience import CircuitBreaker, CircuitState, retry

__version__ = "1.0.0"
