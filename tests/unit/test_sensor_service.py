"""
Unit Tests — SensorService with In-Memory Adapters.

INTERVIEW POINT: "These tests prove the hexagonal architecture payoff.
The entire business logic is tested WITHOUT a database, network, or
any infrastructure. Tests run in milliseconds and never flake."
"""
import pytest
from datetime import datetime

from dat_service_lib import (
    SensorReading, SensorUnit, SensorThreshold, ReadingStatus,
    SensorService,
    InMemoryReadingRepo, InMemoryThresholdRepo,
    LogAlertNotifier, PrometheusMetrics,
    InvalidReadingError, ReadingOutOfRangeError,
    validate_sensor_id, validate_reading_value,
)


class TestSensorServiceProcessing:
    """Test the core processing pipeline."""

    def test_valid_reading_is_saved(self, sensor_service, reading_repo, sample_reading):
        result = sensor_service.process_reading(sample_reading)
        assert result.status == ReadingStatus.VALID
        assert len(reading_repo) == 1

    def test_anomaly_reading_detected_by_threshold(
        self, sensor_service, reading_repo, anomaly_reading
    ):
        result = sensor_service.process_reading(anomaly_reading)
        assert result.status == ReadingStatus.ANOMALY
        assert "anomaly" in result.tags
        assert len(reading_repo) == 1

    def test_invalid_sensor_id_rejected(self, sensor_service):
        bad_reading = SensorReading("", 50.0, SensorUnit.FAHRENHEIT)
        with pytest.raises(InvalidReadingError):
            sensor_service.process_reading(bad_reading)

    def test_out_of_range_value_rejected(self, sensor_service):
        bad_reading = SensorReading("TEMP-01", 999.9, SensorUnit.FAHRENHEIT)
        with pytest.raises(ReadingOutOfRangeError):
            sensor_service.process_reading(bad_reading)

    def test_metrics_incremented_on_valid(
        self, sensor_service, metrics, sample_reading
    ):
        sensor_service.process_reading(sample_reading)
        counter = metrics.get_counter(
            "readings_processed_total",
            {"sensor_id": "TEMP-01", "status": "valid"}
        )
        assert counter == 1

    def test_metrics_incremented_on_anomaly(
        self, sensor_service, metrics, anomaly_reading
    ):
        sensor_service.process_reading(anomaly_reading)
        counter = metrics.get_counter(
            "readings_processed_total",
            {"sensor_id": "TEMP-01", "status": "anomaly"}
        )
        assert counter == 1


class TestBatchProcessing:
    """Test batch processing with error isolation."""

    def test_batch_processes_all_valid(self, sensor_service):
        readings = [
            SensorReading("TEMP-01", 72.0, SensorUnit.FAHRENHEIT),
            SensorReading("TEMP-01", 73.0, SensorUnit.FAHRENHEIT),
            SensorReading("VOLT-01", 12.0, SensorUnit.VOLTS),
        ]
        result = sensor_service.process_batch(readings)
        assert result.total_processed == 3
        assert result.valid_count == 3
        assert result.invalid_count == 0

    def test_batch_isolates_errors(self, sensor_service):
        """One bad reading doesn't stop the batch."""
        readings = [
            SensorReading("TEMP-01", 72.0, SensorUnit.FAHRENHEIT),
            SensorReading("", 50.0, SensorUnit.FAHRENHEIT),  # invalid
            SensorReading("TEMP-01", 73.0, SensorUnit.FAHRENHEIT),
        ]
        result = sensor_service.process_batch(readings)
        assert result.total_processed == 3
        assert result.valid_count == 2
        assert result.invalid_count == 1
        assert len(result.errors) == 1

    def test_batch_detects_anomalies(self, sensor_service):
        readings = [
            SensorReading("TEMP-01", 72.0, SensorUnit.FAHRENHEIT),
            SensorReading("TEMP-01", 95.0, SensorUnit.FAHRENHEIT),  # anomaly
        ]
        result = sensor_service.process_batch(readings)
        assert result.anomaly_count == 1
        assert result.valid_count == 1

    def test_empty_batch(self, sensor_service):
        result = sensor_service.process_batch([])
        assert result.total_processed == 0
        assert result.success_rate == 0.0


class TestQueryOperations:
    """Test data retrieval methods."""

    def test_get_latest_reading(self, sensor_service, reading_repo):
        r1 = SensorReading("TEMP-01", 72.0, SensorUnit.FAHRENHEIT)
        r2 = SensorReading("TEMP-01", 73.0, SensorUnit.FAHRENHEIT)
        sensor_service.process_reading(r1)
        sensor_service.process_reading(r2)

        latest = sensor_service.get_latest_reading("TEMP-01")
        assert latest is not None
        assert latest.value == 73.0

    def test_get_latest_nonexistent_sensor(self, sensor_service):
        result = sensor_service.get_latest_reading("NONEXISTENT-99")
        assert result is None

    def test_get_stats(self, sensor_service, seeded_repo):
        # seeded_repo already has 20 TEMP-01 readings
        sensor_service._readings = seeded_repo
        stats = sensor_service.get_sensor_stats("TEMP-01", hours=24)
        assert stats is not None
        assert stats.count == 20
        assert 65 < stats.mean < 78  # roughly around 72


class TestValidators:
    """Test domain validation functions."""

    @pytest.mark.parametrize("sensor_id,expected", [
        ("TEMP-01", "TEMP-01"),
        ("VOLT-02", "VOLT-02"),
        ("temp-01", "TEMP-01"),   # auto-uppercased
        ("PRES-1", "PRES-1"),
        ("AB-1234", "AB-1234"),
    ])
    def test_valid_sensor_ids(self, sensor_id, expected):
        assert validate_sensor_id(sensor_id) == expected

    @pytest.mark.parametrize("sensor_id", [
        "",
        "INVALID",       # no number
        "A-1",           # prefix too short
        "123-ABC",       # starts with number
    ])
    def test_invalid_sensor_ids(self, sensor_id):
        with pytest.raises(InvalidReadingError):
            validate_sensor_id(sensor_id)

    @pytest.mark.parametrize("value,unit,valid", [
        (72.5, SensorUnit.FAHRENHEIT, True),
        (-50.0, SensorUnit.FAHRENHEIT, True),   # boundary
        (500.0, SensorUnit.FAHRENHEIT, True),    # boundary
        (501.0, SensorUnit.FAHRENHEIT, False),   # over
        (-51.0, SensorUnit.FAHRENHEIT, False),   # under
        (12.0, SensorUnit.VOLTS, True),
        (-1.0, SensorUnit.VOLTS, False),         # negative voltage
        (3000.0, SensorUnit.PSI, True),
    ])
    def test_value_range_validation(self, value, unit, valid):
        if valid:
            result = validate_reading_value("TEST-01", value, unit)
            assert result == value
        else:
            with pytest.raises(ReadingOutOfRangeError):
                validate_reading_value("TEST-01", value, unit)


class TestInMemoryRepository:
    """Test the in-memory adapter directly."""

    def test_save_and_retrieve(self, reading_repo):
        reading = SensorReading("TEMP-01", 72.5, SensorUnit.FAHRENHEIT)
        reading_repo.save(reading)
        results = reading_repo.get_by_sensor("TEMP-01")
        assert len(results) == 1
        assert results[0].value == 72.5

    def test_batch_save(self, reading_repo):
        readings = [
            SensorReading("TEMP-01", 72.0, SensorUnit.FAHRENHEIT),
            SensorReading("TEMP-01", 73.0, SensorUnit.FAHRENHEIT),
        ]
        count = reading_repo.save_batch(readings)
        assert count == 2
        assert len(reading_repo) == 2

    def test_stats_computation(self, seeded_repo):
        stats = seeded_repo.get_stats("TEMP-01")
        assert stats is not None
        assert stats.count == 20
        assert stats.min_value <= stats.mean <= stats.max_value

    def test_clear(self, reading_repo):
        reading_repo.save(SensorReading("TEMP-01", 72.0, SensorUnit.FAHRENHEIT))
        assert len(reading_repo) == 1
        reading_repo.clear()
        assert len(reading_repo) == 0


class TestCircuitBreaker:
    """Test circuit breaker resilience pattern."""

    def test_circuit_stays_closed_on_success(self):
        from dat_service_lib import CircuitBreaker, CircuitState
        cb = CircuitBreaker("test-svc", failure_threshold=3)
        result = cb.call(lambda: "ok")
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED

    def test_circuit_opens_after_threshold(self):
        from dat_service_lib import CircuitBreaker, CircuitState, CircuitOpenError
        cb = CircuitBreaker("test-svc", failure_threshold=2)

        for _ in range(2):
            try:
                cb.call(lambda: (_ for _ in ()).throw(ConnectionError("fail")))
            except ConnectionError:
                pass

        assert cb.state == CircuitState.OPEN

        with pytest.raises(CircuitOpenError):
            cb.call(lambda: "should not execute")

    def test_circuit_recovers_after_timeout(self):
        import time
        from dat_service_lib import CircuitBreaker, CircuitState
        cb = CircuitBreaker("test-svc", failure_threshold=1, reset_timeout_seconds=0.1)

        try:
            cb.call(lambda: (_ for _ in ()).throw(ConnectionError("fail")))
        except ConnectionError:
            pass

        assert cb.state == CircuitState.OPEN
        time.sleep(0.15)  # wait for reset timeout
        assert cb.state == CircuitState.HALF_OPEN


class TestDomainModels:
    """Test domain model behavior."""

    def test_reading_to_dict_roundtrip(self):
        original = SensorReading(
            "TEMP-01", 72.5, SensorUnit.FAHRENHEIT,
            tags=["test"], metadata={"source": "demo"},
        )
        d = original.to_dict()
        restored = SensorReading.from_dict(d)
        assert restored.sensor_id == original.sensor_id
        assert restored.value == original.value
        assert restored.unit == original.unit
        assert restored.tags == original.tags

    def test_mark_as_anomaly(self):
        reading = SensorReading("TEMP-01", 95.0, SensorUnit.FAHRENHEIT)
        anomaly = reading.mark_as_anomaly()
        assert anomaly.status == ReadingStatus.ANOMALY
        assert "anomaly" in anomaly.tags
        # Original unchanged (immutable pattern)
        assert reading.status == ReadingStatus.PENDING

    def test_threshold_range_check(self):
        t = SensorThreshold("TEMP-01", 60.0, 90.0, SensorUnit.FAHRENHEIT)
        assert t.is_within_range(72.5) is True
        assert t.is_within_range(95.0) is False
        assert t.is_within_range(55.0) is False
        assert t.is_within_range(60.0) is True   # boundary
        assert t.is_within_range(90.0) is True   # boundary
