"""
Observability Adapters — Structured Logging & Prometheus Metrics.

INTERVIEW POINT: "Every service gets observability for free by using
this library. One import, one call to setup_logging(), and you have
structured JSON logs with correlation IDs that ship cleanly to Loki
via Fluent Bit without regex parsing."
"""
import logging
import json
import uuid
import sys
from datetime import datetime
from typing import Optional, Dict, Any

from ...core.ports.interfaces import MetricsEmitter


# ═══════════════════════════════════════════════════════════════
# Structured Logging Setup
# ═══════════════════════════════════════════════════════════════

class JSONFormatter(logging.Formatter):
    """
    Formats log records as JSON — ships cleanly to ELK/Loki.

    INTERVIEW POINT: "JSON-formatted logs are machine-parseable.
    No regex needed in the log pipeline. Every field is queryable
    in Grafana/Kibana immediately."
    """

    def __init__(self, service_name: str = "dat-service"):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "service": self.service_name,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add correlation ID if present
        if hasattr(record, "correlation_id"):
            log_entry["correlation_id"] = record.correlation_id

        # Add extra fields
        if hasattr(record, "sensor_id"):
            log_entry["sensor_id"] = record.sensor_id

        # Include any extra dict passed via extra={}
        for key in ["sensor_id", "value", "error", "duration",
                     "status", "context", "correlation_id",
                     "severity", "alert_message", "alert_type",
                     "total", "valid", "anomalies", "invalid",
                     "success_rate", "z_score", "mean", "std_dev",
                     "threshold_min", "threshold_max", "channel"]:
            val = getattr(record, key, None)
            if val is not None and key not in log_entry:
                log_entry[key] = val

        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = str(record.exc_info[1])
            log_entry["exception_type"] = type(record.exc_info[1]).__name__

        return json.dumps(log_entry, default=str)


def setup_logging(
    service_name: str = "dat-service",
    level: str = "INFO",
    json_output: bool = True,
) -> logging.Logger:
    """
    One-call logging setup for any DAT service.

    Usage:
        from dat_service_lib.adapters.observability.logging import setup_logging
        logger = setup_logging("sensor-processor", level="INFO")

    INTERVIEW POINT: "One function call gives every service consistent,
    structured, correlation-ID-aware logging. No team configures logging
    differently. That's the 'standardize' in 5S."
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)

    if json_output:
        handler.setFormatter(JSONFormatter(service_name))
    else:
        handler.setFormatter(logging.Formatter(
            f"%(asctime)s | {service_name} | %(levelname)s | %(name)s | %(message)s"
        ))

    root_logger.addHandler(handler)
    return root_logger


def generate_correlation_id() -> str:
    """Generate a unique correlation ID for request tracing."""
    return str(uuid.uuid4())[:8]


# ═══════════════════════════════════════════════════════════════
# Prometheus Metrics Adapter
# ═══════════════════════════════════════════════════════════════

class PrometheusMetrics(MetricsEmitter):
    """
    Prometheus metrics adapter — exposes /metrics endpoint.

    INTERVIEW POINT: "I instrument services with RED metrics:
    Rate (requests/sec), Errors (error rate), Duration (latency).
    Plus business metrics: readings processed, anomalies detected."
    """

    def __init__(self) -> None:
        self._counters: Dict[str, float] = {}
        self._histograms: Dict[str, list] = {}
        self._gauges: Dict[str, float] = {}
        # In production, use prometheus_client library:
        # from prometheus_client import Counter, Histogram, Gauge

    def increment_counter(
        self, name: str, labels: Optional[Dict[str, str]] = None
    ) -> None:
        key = self._make_key(name, labels)
        self._counters[key] = self._counters.get(key, 0) + 1

    def observe_histogram(
        self, name: str, value: float,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        key = self._make_key(name, labels)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)

    def set_gauge(
        self, name: str, value: float,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        key = self._make_key(name, labels)
        self._gauges[key] = value

    def get_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Test helper — read counter value."""
        return self._counters.get(self._make_key(name, labels), 0)

    def get_all_metrics(self) -> Dict[str, Any]:
        """Test helper — dump all metrics."""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histogram_counts": {k: len(v) for k, v in self._histograms.items()},
        }

    @staticmethod
    def _make_key(name: str, labels: Optional[Dict[str, str]] = None) -> str:
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"


class NoOpMetrics(MetricsEmitter):
    """No-op metrics — used when metrics are disabled."""

    def increment_counter(self, name, labels=None): pass
    def observe_histogram(self, name, value, labels=None): pass
    def set_gauge(self, name, value, labels=None): pass
