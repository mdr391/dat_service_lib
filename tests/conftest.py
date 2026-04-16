"""
Shared Test Fixtures — pytest conftest.py

"""
import pytest
from datetime import datetime, timedelta

from dat_service_lib import (
    SensorReading, SensorUnit, SensorThreshold, ReadingStatus,
    SensorService,
    InMemoryReadingRepo, InMemoryThresholdRepo,
    LogAlertNotifier, PrometheusMetrics,
)


@pytest.fixture
def reading_repo():
    """Fresh in-memory reading repository for each test."""
    return InMemoryReadingRepo()


@pytest.fixture
def threshold_repo():
    """Fresh threshold repository with standard configs."""
    repo = InMemoryThresholdRepo()
    repo.save_threshold(SensorThreshold("TEMP-01", 60.0, 90.0, SensorUnit.FAHRENHEIT))
    repo.save_threshold(SensorThreshold("VOLT-01", 10.0, 14.0, SensorUnit.VOLTS))
    repo.save_threshold(SensorThreshold("PRES-01", 2800.0, 3200.0, SensorUnit.PSI))
    return repo


@pytest.fixture
def alerter():
    """Log-based alerter for test verification."""
    return LogAlertNotifier()


@pytest.fixture
def metrics():
    """In-memory metrics for test assertions."""
    return PrometheusMetrics()


@pytest.fixture
def sensor_service(reading_repo, threshold_repo, alerter, metrics):
    """Fully wired SensorService with in-memory adapters."""
    return SensorService(
        reading_repo=reading_repo,
        threshold_repo=threshold_repo,
        alerter=alerter,
        metrics=metrics,
        anomaly_z_threshold=2.0,
    )


@pytest.fixture
def sample_reading():
    """A valid normal reading."""
    return SensorReading(
        sensor_id="TEMP-01",
        value=72.5,
        unit=SensorUnit.FAHRENHEIT,
        correlation_id="test-001",
    )


@pytest.fixture
def anomaly_reading():
    """A reading that exceeds threshold."""
    return SensorReading(
        sensor_id="TEMP-01",
        value=95.2,
        unit=SensorUnit.FAHRENHEIT,
        correlation_id="test-002",
        tags=["factory-a"],
    )


@pytest.fixture
def seeded_repo(reading_repo):
    """Repository pre-loaded with 20 readings for stats testing."""
    import random
    random.seed(42)
    for i in range(20):
        reading = SensorReading(
            sensor_id="TEMP-01",
            value=round(72.0 + random.gauss(0, 2), 2),
            unit=SensorUnit.FAHRENHEIT,
            timestamp=datetime.utcnow() - timedelta(hours=20 - i),
            status=ReadingStatus.VALID,
        )
        reading_repo.save(reading)
    return reading_repo
