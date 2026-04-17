# dat-service-lib

[![CI](https://github.com/mdr391/dat_service_lib/actions/workflows/ci.yml/badge.svg)](https://github.com/mdr391/dat_service_lib/actions/workflows/ci.yml)

A production-grade shared Python service library built on **Hexagonal Architecture** (Ports & Adapters). Designed for sensor telemetry pipelines where domain logic must remain independent of infrastructure — swappable persistence, alerting, and observability without touching business rules.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        EXTERNAL WORLD                            │
│   gRPC Clients  │  REST Clients  │  Kafka Events  │  Cron Jobs   │
└───────┬─────────┴───────┬────────┴───────┬────────┴──────┬───────┘
        │                 │                │               │
        ▼                 ▼                ▼               ▼
┌──────────────────────────────────────────────────────────────────┐
│                    ADAPTERS (Infrastructure)                     │
│  ┌─────────────┐ ┌──────────────┐ ┌────────────┐ ┌───────────┐  │
│  │ gRPC Handler│ │ FastAPI      │ │ Kafka      │ │ Scheduler │  │
│  │ (inbound)   │ │ Handler      │ │ Consumer   │ │ (inbound) │  │
│  └──────┬──────┘ └──────┬───────┘ └─────┬──────┘ └─────┬─────┘  │
│         └───────────────┴───────────────┴──────────────┘         │
│                         │                                        │
│  ┌──────────────────────▼───────────────────────────────────┐    │
│  │              SERVICE LAYER (Orchestration)               │    │
│  │         sensor_service.py  │  alert_service.py           │    │
│  └──────────────────────┬───────────────────────────────────┘    │
│                         │                                        │
│  ┌──────────────────────▼───────────────────────────────────┐    │
│  │              DOMAIN (Pure Business Logic)                │    │
│  │   SensorReading  │  AnomalyDetector  │  BusinessRules    │    │
│  │   NO infrastructure imports — pure Python + dataclasses  │    │
│  └──────────────────────┬───────────────────────────────────┘    │
│                         │  (depends on PORTS, not adapters)      │
│  ┌──────────────────────▼───────────────────────────────────┐    │
│  │                  PORTS (Interfaces/ABCs)                  │    │
│  │  ReadingRepository │ AlertNotifier │ MetricsEmitter │ ... │    │
│  └──────────┬─────────┴──────┬────────┴──────┬──────────────┘    │
│             │                │               │                   │
│  ┌──────────▼───┐ ┌──────────▼───┐ ┌────────▼───────┐           │
│  │ PostgreSQL   │ │ Slack Alert  │ │ Prometheus     │           │
│  │ Adapter      │ │ Adapter      │ │ Adapter        │           │
│  │ (outbound)   │ │ (outbound)   │ │ (outbound)     │           │
│  └──────────────┘ └──────────────┘ └────────────────┘           │
│                    ADAPTERS (Infrastructure)                     │
└──────────────────────────────────────────────────────────────────┘
```

The domain layer has zero knowledge of PostgreSQL, gRPC, or Consul. Unit tests run entirely against in-memory adapters — no database, no network, no Docker required.

---

## Quick Start

```bash
pip install -e ".[dev]"
python -m examples.run_demo     # full working demo
pytest tests/ -v                # run all tests
```

---

## Usage

Wire up the service with your choice of adapters and start processing readings — swapping PostgreSQL for in-memory changes nothing in your business logic:

```python
from dat_service_lib import (
    SensorReading, SensorThreshold, SensorUnit,
    SensorService,
    InMemoryReadingRepo, InMemoryThresholdRepo,
    LogAlertNotifier, PrometheusMetrics,
)

# 1. Choose adapters (swap PostgresReadingRepo in production — zero code change)
repo = InMemoryReadingRepo()
thresholds = InMemoryThresholdRepo()
thresholds.save_threshold(SensorThreshold("TEMP-01", min_value=60.0, max_value=90.0, unit=SensorUnit.FAHRENHEIT))

# 2. Wire the service via dependency injection
service = SensorService(
    reading_repo=repo,
    threshold_repo=thresholds,
    alerter=LogAlertNotifier(),
    metrics=PrometheusMetrics(),
)

# 3. Process a reading — validation, anomaly detection, alerting, metrics in one call
reading = SensorReading("TEMP-01", value=95.2, unit=SensorUnit.FAHRENHEIT)
result = service.process_reading(reading)
print(result.status)   # ReadingStatus.ANOMALY — threshold exceeded, alert fired

# 4. Batch processing with error isolation
batch_result = service.process_batch([...])
print(f"{batch_result.anomaly_count} anomalies / {batch_result.total_processed} total")

# 5. Query stats
stats = service.get_sensor_stats("TEMP-01", hours=24)
print(f"mean={stats.mean:.2f}, std={stats.std_dev:.2f}, anomalies={stats.anomaly_count}")
```

See [`examples/run_demo.py`](examples/run_demo.py) for a full walkthrough of all patterns.

---

## Project Structure

```
dat_service_lib/
├── dat_service_lib/
│   ├── core/
│   │   ├── domain/
│   │   │   ├── models.py          # SensorReading, SensorThreshold, etc.
│   │   │   ├── exceptions.py      # Typed exception hierarchy
│   │   │   └── validators.py      # Pure validation functions
│   │   ├── ports/
│   │   │   └── interfaces.py      # ABCs: ReadingRepository, AlertNotifier, ...
│   │   └── services/
│   │       └── sensor_service.py  # Business logic orchestration
│   ├── adapters/
│   │   ├── persistence/
│   │   │   ├── postgres_repo.py   # PostgreSQL adapter
│   │   │   └── in_memory_repo.py  # In-memory adapter (tests / local dev)
│   │   ├── messaging/
│   │   │   └── alert_adapters.py  # Slack, Log, Composite alert adapters
│   │   ├── observability/
│   │   │   └── logging.py         # Structured JSON logging + Prometheus RED metrics
│   │   └── config/
│   │       └── settings.py        # Env-var config with dataclass defaults
│   └── utils/
│       └── resilience.py          # Circuit breaker + retry with exponential backoff
├── tests/
│   ├── unit/                      # In-memory adapters — no infrastructure required
│   └── integration/               # Real PostgreSQL via testcontainers
└── examples/
    └── run_demo.py                # End-to-end walkthrough
```

---

## Design Patterns

| Pattern | Where | Why |
|---|---|---|
| Repository | `ports/interfaces.py` + `adapters/persistence/` | Decouple domain from storage engine |
| Strategy | `AnomalyDetector` protocol | Swap detection algorithms at runtime |
| Composite | `CompositeAlertNotifier` | Fan out to multiple channels without changing call sites |
| Circuit Breaker | `utils/resilience.py` | Prevent cascading failures to downstream services |
| Decorator | `@retry` | Exponential backoff with jitter on transient errors |
| Dependency Injection | `SensorService.__init__` | All infrastructure injected — never created internally |

---

## Testing Strategy

```
Unit tests (fast, no infra)     → tests/unit/
  └── SensorService + all domain logic tested with InMemoryReadingRepo

Integration tests (real DB)     → tests/integration/
  └── PostgresReadingRepo tested against real PostgreSQL (testcontainers)
```

Run only unit tests:
```bash
pytest tests/unit/ -v
```

---

## Configuration

All settings are loaded from environment variables with code defaults:

```bash
SERVICE_NAME=my-service
GRPC_PORT=50051
DB_DSN=postgresql://user:pass@host:5432/db
LOG_LEVEL=INFO
LOG_JSON=true
METRICS_PORT=9090
ANOMALY_Z_THRESHOLD=2.0
```

---

## License

MIT
