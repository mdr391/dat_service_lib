"""
Sensor Service — Business Logic Orchestration.

INTERVIEW TALKING POINT:
"This is the service layer — it orchestrates domain logic using ports.
Notice it depends on ReadingRepository and AlertNotifier (abstractions),
NOT on PostgresRepo or SlackNotifier (implementations). That's why
I can test the entire business logic with in-memory fakes."

This layer:
- Validates incoming readings
- Detects anomalies using configurable strategies
- Persists validated data
- Sends alerts when needed
- Emits metrics
- NEVER touches infrastructure directly
"""
import logging
import statistics
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from ..ports.interfaces import (
    ReadingRepository,
    ThresholdRepository,
    AlertNotifier,
    MetricsEmitter,
    AnomalyDetector,
)
from ..domain.models import (
    SensorReading, SensorStats, ReadingStatus, ProcessingResult,
)
from ..domain.validators import validate_reading, is_statistical_anomaly
from ..domain.exceptions import (
    SensorError, InvalidReadingError, ReadingOutOfRangeError,
)

logger = logging.getLogger(__name__)


class SensorService:
    """
    Core business logic for processing sensor readings.

    DESIGN PATTERN: Service Layer + Dependency Injection
    All dependencies are injected via constructor — never created internally.
    """

    def __init__(
        self,
        reading_repo: ReadingRepository,
        threshold_repo: ThresholdRepository,
        alerter: AlertNotifier,
        metrics: Optional[MetricsEmitter] = None,
        anomaly_detector: Optional[AnomalyDetector] = None,
        anomaly_z_threshold: float = 2.0,
    ):
        # Dependencies injected — not created here
        self._readings = reading_repo
        self._thresholds = threshold_repo
        self._alerter = alerter
        self._metrics = metrics
        self._detector = anomaly_detector
        self._z_threshold = anomaly_z_threshold

    def process_reading(self, reading: SensorReading) -> SensorReading:
        """
        Process a single sensor reading:
        1. Validate the reading
        2. Check against thresholds
        3. Run anomaly detection
        4. Persist the reading
        5. Alert if anomaly
        6. Emit metrics

        Returns the processed reading with updated status.
        """
        # Step 1: Validate
        try:
            validate_reading(reading)
        except SensorError as e:
            logger.warning("validation_failed", extra={
                "sensor_id": reading.sensor_id,
                "error": str(e),
                "correlation_id": reading.correlation_id,
            })
            if self._metrics:
                self._metrics.increment_counter(
                    "readings_invalid_total",
                    {"sensor_id": reading.sensor_id}
                )
            raise

        # Step 2: Check static thresholds
        threshold = self._thresholds.get_threshold(reading.sensor_id)
        is_anomaly = False

        if threshold and not threshold.is_within_range(reading.value):
            is_anomaly = True
            logger.info("threshold_anomaly_detected", extra={
                "sensor_id": reading.sensor_id,
                "value": reading.value,
                "threshold_min": threshold.min_value,
                "threshold_max": threshold.max_value,
            })

        # Step 3: Statistical anomaly detection
        if not is_anomaly:
            stats = self._readings.get_stats(reading.sensor_id)
            if stats and stats.count > 10:  # need enough data
                anomaly_flag, z_score = is_statistical_anomaly(
                    reading.value, stats.mean, stats.std_dev, self._z_threshold
                )
                if anomaly_flag:
                    is_anomaly = True
                    reading.metadata["z_score"] = z_score
                    logger.info("statistical_anomaly_detected", extra={
                        "sensor_id": reading.sensor_id,
                        "value": reading.value,
                        "z_score": z_score,
                        "mean": stats.mean,
                        "std_dev": stats.std_dev,
                    })

        # Step 4: Update status and persist
        if is_anomaly:
            reading = reading.mark_as_anomaly()
        else:
            reading = reading.mark_as_valid()

        self._readings.save(reading)

        # Step 5: Alert if anomaly
        if is_anomaly:
            self._alerter.send_alert(
                sensor_id=reading.sensor_id,
                message=f"Anomaly detected: value={reading.value} {reading.unit.value}",
                severity="warning",
                context=reading.to_dict(),
            )

        # Step 6: Emit metrics
        if self._metrics:
            self._metrics.increment_counter(
                "readings_processed_total",
                {"sensor_id": reading.sensor_id, "status": reading.status.value}
            )
            self._metrics.observe_histogram(
                "reading_value",
                reading.value,
                {"sensor_id": reading.sensor_id}
            )

        return reading

    def process_batch(self, readings: List[SensorReading]) -> ProcessingResult:
        """
        Process a batch of readings with error isolation.
        One bad reading doesn't stop the batch.

        INTERVIEW POINT: "Batch processing with error isolation —
        each reading is processed independently. Failures are logged
        and counted, not propagated. This is critical for sensor data
        where one bad reading shouldn't block thousands of good ones."
        """
        result = ProcessingResult(
            total_processed=len(readings),
            valid_count=0,
            anomaly_count=0,
            invalid_count=0,
        )

        for reading in readings:
            try:
                processed = self.process_reading(reading)
                if processed.status == ReadingStatus.ANOMALY:
                    result.anomaly_count += 1
                else:
                    result.valid_count += 1
            except SensorError as e:
                result.invalid_count += 1
                result.errors.append(f"{reading.sensor_id}: {str(e)}")
                logger.warning("batch_reading_failed", extra={
                    "sensor_id": reading.sensor_id,
                    "error": str(e),
                })

        logger.info("batch_processing_complete", extra={
            "total": result.total_processed,
            "valid": result.valid_count,
            "anomalies": result.anomaly_count,
            "invalid": result.invalid_count,
            "success_rate": f"{result.success_rate:.1%}",
        })

        return result

    def get_sensor_stats(
        self,
        sensor_id: str,
        hours: int = 24,
    ) -> Optional[SensorStats]:
        """Get statistics for a sensor over the last N hours."""
        start = datetime.utcnow() - timedelta(hours=hours)
        return self._readings.get_stats(sensor_id, start=start)

    def get_latest_reading(self, sensor_id: str) -> Optional[SensorReading]:
        """Get the most recent reading for a sensor."""
        return self._readings.get_latest(sensor_id)

    def get_readings_history(
        self,
        sensor_id: str,
        hours: int = 24,
        limit: int = 100,
    ) -> List[SensorReading]:
        """Get reading history for a sensor."""
        start = datetime.utcnow() - timedelta(hours=hours)
        return self._readings.get_by_sensor(
            sensor_id, start=start, limit=limit
        )
