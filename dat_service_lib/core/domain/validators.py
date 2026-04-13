"""
Domain Validators — Pure functions, no infrastructure dependencies.

INTERVIEW POINT: "Validation is a domain concern, not an adapter concern.
These functions know the business rules (temperature ranges, sensor ID
formats) but nothing about how data arrives or is stored."
"""
import re
from typing import Optional, Tuple
from .models import SensorReading, SensorUnit
from .exceptions import InvalidReadingError, ReadingOutOfRangeError

# ── Physical range limits per sensor unit ─────────────────────
UNIT_RANGES = {
    SensorUnit.FAHRENHEIT: (-50.0, 500.0),
    SensorUnit.CELSIUS: (-50.0, 260.0),
    SensorUnit.VOLTS: (0.0, 480.0),
    SensorUnit.PSI: (0.0, 15000.0),
    SensorUnit.PERCENT: (0.0, 100.0),
    SensorUnit.MM_PER_SEC: (0.0, 1000.0),
}

SENSOR_ID_PATTERN = re.compile(r"^[A-Z]{2,8}-\d{1,4}$")


def validate_sensor_id(sensor_id: str) -> str:
    """
    Validate sensor ID format: LETTERS-DIGITS (e.g., TEMP-01, VOLT-02).
    Returns the validated ID or raises InvalidReadingError.
    """
    if not sensor_id or not isinstance(sensor_id, str):
        raise InvalidReadingError(str(sensor_id), "sensor_id must be a non-empty string")

    sensor_id = sensor_id.strip().upper()

    if not SENSOR_ID_PATTERN.match(sensor_id):
        raise InvalidReadingError(
            sensor_id,
            f"sensor_id must match pattern LETTERS-DIGITS (e.g., TEMP-01), got '{sensor_id}'"
        )
    return sensor_id


def validate_reading_value(
    sensor_id: str,
    value: float,
    unit: SensorUnit,
) -> float:
    """
    Validate that a reading value is within physical range for its unit.
    Returns the validated value or raises ReadingOutOfRangeError.
    """
    if not isinstance(value, (int, float)):
        raise InvalidReadingError(sensor_id, f"value must be numeric, got {type(value)}")

    if value != value:  # NaN check
        raise InvalidReadingError(sensor_id, "value is NaN")

    min_val, max_val = UNIT_RANGES.get(unit, (-float("inf"), float("inf")))

    if value < min_val or value > max_val:
        raise ReadingOutOfRangeError(sensor_id, value, min_val, max_val)

    return value


def validate_reading(reading: SensorReading) -> SensorReading:
    """
    Full validation of a SensorReading.
    Returns validated reading or raises appropriate exception.
    """
    validate_sensor_id(reading.sensor_id)
    validate_reading_value(reading.sensor_id, reading.value, reading.unit)
    return reading


def compute_z_score(value: float, mean: float, std_dev: float) -> Optional[float]:
    """Compute Z-score for anomaly detection. Returns None if std_dev is 0."""
    if std_dev == 0:
        return None
    return abs((value - mean) / std_dev)


def is_statistical_anomaly(
    value: float,
    mean: float,
    std_dev: float,
    threshold: float = 2.0,
) -> Tuple[bool, Optional[float]]:
    """
    Determine if a value is a statistical anomaly based on Z-score.
    Returns (is_anomaly, z_score).
    """
    z = compute_z_score(value, mean, std_dev)
    if z is None:
        return False, None
    return z > threshold, z
