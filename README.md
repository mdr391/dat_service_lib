# dat-service-lib

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
