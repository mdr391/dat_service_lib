"""
DAT Service Library — Full Working Demo.

RUN THIS:
    cd dat_service_lib
    python -m examples.run_demo

This demonstrates the complete hexagonal architecture:
1. Configure the service with environment-based settings
2. Wire up adapters (in-memory for this demo, PostgreSQL in production)
3. Process sensor readings through the service layer
4. See validation, anomaly detection, alerting, and metrics in action
5. Show how swapping adapters changes NOTHING in business logic
"""
import sys
import os
import random
from datetime import datetime, timedelta
from typing import List

# Add parent to path for running as script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dat_service_lib import (
    # Domain models
    SensorReading, SensorUnit, SensorThreshold, ReadingStatus,
    # Service layer
    SensorService,
    # Adapters — we choose which ones to wire up
    InMemoryReadingRepo, InMemoryThresholdRepo,
    LogAlertNotifier, SlackAlertNotifier, CompositeAlertNotifier,
    PrometheusMetrics,
    # Observability
    setup_logging, generate_correlation_id,
    # Config
    ServiceConfig,
    # Exceptions
    SensorError, InvalidReadingError, ReadingOutOfRangeError,
    # Utilities
    CircuitBreaker, retry,
)


def banner(title: str) -> None:
    print(f"\n{'═' * 65}")
    print(f"  {title}")
    print(f"{'═' * 65}")


def demo_1_composition_root():
    """
    """
    banner("DEMO 1: Composition Root — Wiring Adapters to Ports")

    # ── Load config from environment (or defaults) ────────────
    config = ServiceConfig.from_env()
    print(f"  Config loaded:")
    print(f"    service: {config.service_name}")
    print(f"    log_level: {config.log_level}")
    print(f"    anomaly_threshold: {config.anomaly_z_threshold}")

    # ── Choose adapters ───────────────────────────────────────
    # In production:
    #   reading_repo = PostgresReadingRepo(connection_pool)
    #   alerter = SlackAlertNotifier("https://hooks.slack.com/...")
    #   metrics = PrometheusMetrics()  # real prometheus_client
    #
    # For this demo (and unit tests):
    reading_repo = InMemoryReadingRepo()
    threshold_repo = InMemoryThresholdRepo()
    alerter = LogAlertNotifier()       # logs alerts instead of Slack
    metrics = PrometheusMetrics()      # in-memory metrics

    # ── Wire the service (Dependency Injection) ───────────────
    service = SensorService(
        reading_repo=reading_repo,      # PORT: ReadingRepository
        threshold_repo=threshold_repo,  # PORT: ThresholdRepository
        alerter=alerter,                # PORT: AlertNotifier
        metrics=metrics,                # PORT: MetricsEmitter
        anomaly_z_threshold=config.anomaly_z_threshold,
    )

    print(f"\n  ✅ Service wired with:")
    print(f"    ReadingRepository  → {type(reading_repo).__name__}")
    print(f"    ThresholdRepository → {type(threshold_repo).__name__}")
    print(f"    AlertNotifier      → {type(alerter).__name__}")
    print(f"    MetricsEmitter     → {type(metrics).__name__}")
    print(f"\n  The SensorService has NO IDEA these are in-memory fakes.")
    print(f"  Swap PostgresReadingRepo in and business logic is identical.")

    return service, reading_repo, threshold_repo, metrics


def demo_2_configure_thresholds(threshold_repo: InMemoryThresholdRepo):
    """Configure sensor thresholds — business rules for anomaly detection."""
    banner("DEMO 2: Configure Sensor Thresholds")

    thresholds = [
        SensorThreshold("TEMP-01", 60.0, 90.0, SensorUnit.FAHRENHEIT),
        SensorThreshold("TEMP-02", 60.0, 90.0, SensorUnit.FAHRENHEIT),
        SensorThreshold("VOLT-01", 10.0, 14.0, SensorUnit.VOLTS),
        SensorThreshold("PRES-01", 2800.0, 3200.0, SensorUnit.PSI),
        SensorThreshold("HUMD-01", 35.0, 60.0, SensorUnit.PERCENT),
    ]

    for t in thresholds:
        threshold_repo.save_threshold(t)
        print(f"  Configured: {t.sensor_id} [{t.min_value} - {t.max_value}] {t.unit.value}")

    print(f"\n  Total thresholds configured: {len(thresholds)}")


def demo_3_process_readings(service: SensorService):
    """Process individual readings — validation + anomaly detection."""
    banner("DEMO 3: Process Individual Readings")

    test_readings = [
        # Normal readings
        SensorReading("TEMP-01", 72.5, SensorUnit.FAHRENHEIT,
                      correlation_id=generate_correlation_id()),
        SensorReading("TEMP-01", 73.1, SensorUnit.FAHRENHEIT,
                      correlation_id=generate_correlation_id()),
        SensorReading("VOLT-01", 12.1, SensorUnit.VOLTS,
                      correlation_id=generate_correlation_id()),

        # Anomaly — exceeds threshold
        SensorReading("TEMP-01", 95.2, SensorUnit.FAHRENHEIT,
                      correlation_id=generate_correlation_id(),
                      tags=["factory-a", "assembly-line-1"]),

        # Normal
        SensorReading("PRES-01", 3050.0, SensorUnit.PSI,
                      correlation_id=generate_correlation_id()),
    ]

    print(f"  Processing {len(test_readings)} readings...\n")

    for reading in test_readings:
        try:
            result = service.process_reading(reading)
            status_icon = "🔴" if result.status == ReadingStatus.ANOMALY else "✅"
            print(f"  {status_icon} {result.sensor_id}: "
                  f"value={result.value} {result.unit.value} "
                  f"→ {result.status.value}")
        except SensorError as e:
            print(f"  ❌ {reading.sensor_id}: REJECTED — {e}")


def demo_4_batch_processing(service: SensorService):
    """Process a batch of readings with error isolation."""
    banner("DEMO 4: Batch Processing with Error Isolation")

    random.seed(42)
    batch: List[SensorReading] = []

    # Generate 20 readings — mix of valid, anomalies, and invalid
    for i in range(20):
        sensor_id = random.choice(["TEMP-01", "TEMP-02", "VOLT-01", "PRES-01"])
        unit_map = {
            "TEMP-01": SensorUnit.FAHRENHEIT,
            "TEMP-02": SensorUnit.FAHRENHEIT,
            "VOLT-01": SensorUnit.VOLTS,
            "PRES-01": SensorUnit.PSI,
        }

        if i == 5:
            # Invalid — bad sensor ID
            batch.append(SensorReading("", 50.0, SensorUnit.FAHRENHEIT))
        elif i == 12:
            # Out of range — physically impossible temperature
            batch.append(SensorReading("TEMP-01", 999.9, SensorUnit.FAHRENHEIT))
        elif i == 15:
            # Anomaly — exceeds threshold
            batch.append(SensorReading("TEMP-01", 96.5, SensorUnit.FAHRENHEIT))
        else:
            # Normal reading with slight variation
            base_values = {"TEMP-01": 72.0, "TEMP-02": 69.0, "VOLT-01": 12.0, "PRES-01": 3000.0}
            value = base_values[sensor_id] + random.gauss(0, 1.5)
            batch.append(SensorReading(
                sensor_id, round(value, 2), unit_map[sensor_id],
                correlation_id=generate_correlation_id(),
            ))

    print(f"  Processing batch of {len(batch)} readings...\n")
    result = service.process_batch(batch)

    print(f"\n  ── Batch Results ──")
    print(f"  Total processed: {result.total_processed}")
    print(f"  Valid:           {result.valid_count}")
    print(f"  Anomalies:       {result.anomaly_count}")
    print(f"  Invalid:         {result.invalid_count}")
    print(f"  Success rate:    {result.success_rate:.1%}")
    if result.errors:
        print(f"  Errors:")
        for err in result.errors:
            print(f"    ⚠ {err}")


def demo_5_query_and_stats(service: SensorService, reading_repo: InMemoryReadingRepo):
    """Query stored data and compute statistics."""
    banner("DEMO 5: Query Data & Compute Statistics")

    print(f"  Total readings stored: {len(reading_repo)}\n")

    # Get stats for each sensor
    for sensor_id in ["TEMP-01", "TEMP-02", "VOLT-01", "PRES-01"]:
        stats = service.get_sensor_stats(sensor_id, hours=24)
        if stats:
            print(f"  {sensor_id}:")
            print(f"    count={stats.count}, mean={stats.mean:.2f}, "
                  f"std={stats.std_dev:.2f}")
            print(f"    range=[{stats.min_value:.2f}, {stats.max_value:.2f}], "
                  f"anomalies={stats.anomaly_count}")

    # Get latest reading
    print(f"\n  Latest readings:")
    for sensor_id in ["TEMP-01", "VOLT-01"]:
        latest = service.get_latest_reading(sensor_id)
        if latest:
            print(f"    {sensor_id}: {latest.value} {latest.unit.value} "
                  f"({latest.status.value}) at {latest.timestamp.strftime('%H:%M:%S')}")


def demo_6_metrics(metrics: PrometheusMetrics):
    """Show collected metrics."""
    banner("DEMO 6: Observability Metrics")

    all_metrics = metrics.get_all_metrics()
    print("  Counters:")
    for name, value in sorted(all_metrics["counters"].items()):
        print(f"    {name}: {value}")

    print(f"\n  Histogram observation counts:")
    for name, count in sorted(all_metrics["histogram_counts"].items()):
        print(f"    {name}: {count} observations")


def demo_7_circuit_breaker():
    """Demonstrate circuit breaker pattern."""
    banner("DEMO 7: Circuit Breaker Pattern")

    cb = CircuitBreaker(
        service_name="downstream-db",
        failure_threshold=3,
        reset_timeout_seconds=2.0,
    )

    call_count = 0

    def unstable_service():
        nonlocal call_count
        call_count += 1
        if call_count <= 4:
            raise ConnectionError("Connection refused")
        return "SUCCESS"

    print("  Simulating calls to unstable service...\n")

    for i in range(7):
        try:
            result = cb.call(unstable_service)
            print(f"  Call {i+1}: ✅ {result} (state={cb.state.value})")
        except ConnectionError as e:
            print(f"  Call {i+1}: ❌ {e} (state={cb.state.value})")
        except Exception as e:
            print(f"  Call {i+1}: 🔴 CIRCUIT OPEN — {e} (state={cb.state.value})")


def demo_8_retry_decorator():
    """Demonstrate retry with exponential backoff."""
    banner("DEMO 8: Retry with Exponential Backoff")

    attempt_count = 0

    @retry(max_attempts=4, base_delay=0.1, exceptions=(ConnectionError,))
    def flaky_api_call():
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 3:
            raise ConnectionError("Timeout")
        return {"status": "ok", "data": [1, 2, 3]}

    print("  Calling flaky API with retry decorator...\n")
    try:
        result = flaky_api_call()
        print(f"  ✅ Final result: {result}")
        print(f"  Total attempts: {attempt_count}")
    except ConnectionError:
        print(f"  ❌ All retries exhausted after {attempt_count} attempts")


def demo_9_composite_alerter():
    """Demonstrate composite pattern — fan out alerts to multiple channels."""
    banner("DEMO 9: Composite Alert Notifier")

    # Create individual notifiers
    log_notifier = LogAlertNotifier()
    slack_notifier = SlackAlertNotifier(
        webhook_url="https://hooks.slack.com/services/FAKE",
        channel="#dat-alerts",
    )

    # Composite sends to ALL notifiers
    composite = CompositeAlertNotifier([log_notifier, slack_notifier])

    print("  Sending alert through composite notifier...\n")
    composite.send_alert(
        sensor_id="TEMP-01",
        message="Temperature spike detected: 95.2°F",
        severity="critical",
        context={"value": 95.2, "threshold": 90.0},
    )
    print("\n  ✅ Alert sent to both Log and Slack channels")


def demo_10_validation():
    """Demonstrate validation patterns."""
    banner("DEMO 10: Input Validation")

    from dat_service_lib import validate_sensor_id, validate_reading_value

    test_cases = [
        ("TEMP-01", True),
        ("VOLT-02", True),
        ("temp-01", True),      # auto-uppercased
        ("", False),            # empty
        ("INVALID", False),     # missing number
        ("A-1", False),         # too short prefix
        ("TOOLONG-99999", False),  # too long
    ]

    print("  Sensor ID validation:")
    for sensor_id, expected_valid in test_cases:
        try:
            result = validate_sensor_id(sensor_id)
            icon = "✅" if expected_valid else "⚠️ (should have failed)"
            print(f"    {icon} '{sensor_id}' → '{result}'")
        except Exception as e:
            icon = "✅ rejected" if not expected_valid else "❌ (should have passed)"
            print(f"    {icon} '{sensor_id}' → {type(e).__name__}: {e}")

    print(f"\n  Value range validation:")
    value_tests = [
        ("TEMP-01", 72.5, SensorUnit.FAHRENHEIT, True),
        ("TEMP-01", 999.0, SensorUnit.FAHRENHEIT, False),   # out of range
        ("VOLT-01", -5.0, SensorUnit.VOLTS, False),         # negative voltage
        ("PRES-01", 3000.0, SensorUnit.PSI, True),
    ]

    for sensor_id, value, unit, expected_valid in value_tests:
        try:
            validate_reading_value(sensor_id, value, unit)
            icon = "✅"
            print(f"    {icon} {sensor_id}={value} {unit.value}")
        except Exception as e:
            icon = "✅ rejected"
            print(f"    {icon} {sensor_id}={value} {unit.value} → {e}")


# ═══════════════════════════════════════════════════════════════
# MAIN — Run all demos
# ═══════════════════════════════════════════════════════════════

def main():
    print("""
╔═════════════════════════════════════════════════════════════════╗
║  DAT Service Library — Hexagonal Architecture Demo            ║
║  BAE Systems — Principal Python Engineer                      ║
║                                                                ║
║  This demonstrates the complete library architecture:         ║
║  Domain → Ports → Service Layer → Adapters → Utilities        ║
╚═════════════════════════════════════════════════════════════════╝
    """)

    # Setup logging (human-readable for demo, JSON for production)
    setup_logging("dat-demo", level="WARNING", json_output=False)

    # Demo 1: Wire the service
    service, reading_repo, threshold_repo, metrics = demo_1_composition_root()

    # Demo 2: Configure thresholds
    demo_2_configure_thresholds(threshold_repo)

    # Demo 3: Process individual readings
    demo_3_process_readings(service)

    # Demo 4: Batch processing
    demo_4_batch_processing(service)

    # Demo 5: Query and stats
    demo_5_query_and_stats(service, reading_repo)

    # Demo 6: Metrics
    demo_6_metrics(metrics)

    # Demo 7: Circuit breaker
    demo_7_circuit_breaker()

    # Demo 8: Retry
    demo_8_retry_decorator()

    # Demo 9: Composite alerter
    demo_9_composite_alerter()

    # Demo 10: Validation
    demo_10_validation()

    banner("ALL DEMOS COMPLETE ✅")
    print("""
  This library demonstrates:
  ✅ Hexagonal Architecture (Ports & Adapters)
  ✅ Dependency Injection (constructor injection)
  ✅ Repository Pattern (swappable persistence)
  ✅ Strategy Pattern (anomaly detection algorithms)
  ✅ Composite Pattern (multi-channel alerting)
  ✅ Circuit Breaker (resilience)
  ✅ Retry with Exponential Backoff (resilience)
  ✅ Structured Logging (observability)
  ✅ Prometheus Metrics (observability)
  ✅ Input Validation (domain validators)
  ✅ Custom Exception Hierarchy (error handling)
  ✅ Environment-based Configuration (12-factor app)

  To run tests:  python -m pytest tests/ -v
  To see JSON logging: LOG_JSON=true python -m examples.run_demo
    """)


if __name__ == "__main__":
    main()
