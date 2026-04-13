"""
Domain Exceptions — Typed error hierarchy for clean error handling.

INTERVIEW POINT: "I design exception hierarchies so callers can catch
at the right granularity. Catch SensorError for any sensor issue,
or catch SensorNotFoundError for a specific case. This is cleaner
than catching generic Exception and parsing error messages."
"""


class DATServiceError(Exception):
    """Base exception for all DAT service errors."""
    pass


# ── Sensor Errors ─────────────────────────────────────────────

class SensorError(DATServiceError):
    """Base exception for sensor-related operations."""
    pass


class SensorNotFoundError(SensorError):
    """Raised when a sensor ID doesn't exist in the system."""
    def __init__(self, sensor_id: str):
        self.sensor_id = sensor_id
        super().__init__(f"Sensor '{sensor_id}' not found")


class ReadingOutOfRangeError(SensorError):
    """Raised when a reading value exceeds valid physical range."""
    def __init__(self, sensor_id: str, value: float,
                 min_val: float, max_val: float):
        self.sensor_id = sensor_id
        self.value = value
        self.min_val = min_val
        self.max_val = max_val
        super().__init__(
            f"Sensor '{sensor_id}' reading {value} "
            f"out of range [{min_val}, {max_val}]"
        )


class InvalidReadingError(SensorError):
    """Raised when a reading fails validation."""
    def __init__(self, sensor_id: str, reason: str):
        self.sensor_id = sensor_id
        self.reason = reason
        super().__init__(f"Invalid reading for '{sensor_id}': {reason}")


# ── Infrastructure Errors ─────────────────────────────────────

class RepositoryError(DATServiceError):
    """Raised when a data persistence operation fails."""
    pass


class ConnectionError(DATServiceError):
    """Raised when a downstream service connection fails."""
    pass


class AuthenticationError(DATServiceError):
    """Raised when authentication/authorization fails."""
    pass


class CircuitOpenError(DATServiceError):
    """Raised when circuit breaker is open — fail fast."""
    def __init__(self, service_name: str):
        self.service_name = service_name
        super().__init__(
            f"Circuit breaker OPEN for '{service_name}' — failing fast"
        )
