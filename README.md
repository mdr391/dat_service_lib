<<<<<<< HEAD
# dat_service_lib
Dat service library
=======
# DAT Service Library — Hexagonal Architecture Reference Implementation

## For BAE Systems DAT — Principal Python Engineer Interview

This is a **complete, runnable** implementation of the internal shared service library
you'd build as Principal Engineer on the DAT team. It demonstrates:

- **Hexagonal Architecture** (Ports & Adapters)
- **Modular Software Architecture** with 5S principles
- **Shared Library Design** that standardizes cross-cutting concerns
- **Design Patterns**: Repository, Strategy, Factory, Decorator, Circuit Breaker
- **Python 3.8 compatible** (typing imports, no 3.9+ features)

---

## Quick Start

```bash
cd dat_service_lib
pip install -r requirements.txt
python -m examples.run_demo          # Run the full demo
python -m pytest tests/ -v           # Run all tests
```

---

## Architecture Diagram

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
│         │               │               │              │         │
│         ▼               ▼               ▼              ▼         │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │              SERVICE LAYER (Orchestration)               │    │
│  │         sensor_service.py  │  alert_service.py           │    │
│  └──────────────────────┬───────────────────────────────────┘    │
│                         │                                        │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │              DOMAIN (Pure Business Logic)                │    │
│  │   SensorReading  │  AnomalyDetector  │  BusinessRules    │    │
│  │   NO infrastructure imports — pure Python + dataclasses  │    │
│  └──────────────────────┬───────────────────────────────────┘    │
│                         │                                        │
│                         ▼   (depends on PORTS, not adapters)     │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │                  PORTS (Interfaces/ABCs)                  │    │
│  │  ReadingRepository │ AlertNotifier │ MetricsEmitter │ ... │    │
│  └──────────┬─────────┴──────┬────────┴──────┬──────────────┘    │
│             │                │               │                   │
│             ▼                ▼               ▼                   │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────┐           │
│  │ PostgreSQL   │ │ Slack Alert  │ │ Prometheus     │           │
│  │ Adapter      │ │ Adapter      │ │ Adapter        │           │
│  │ (outbound)   │ │ (outbound)   │ │ (outbound)     │           │
│  └──────────────┘ └──────────────┘ └────────────────┘           │
│                    ADAPTERS (Infrastructure)                     │
└──────────────────────────────────────────────────────────────────┘
```

---

## Key Interview Talking Points

### 1. "Why Hexagonal Architecture?"
> "The domain layer has ZERO knowledge of PostgreSQL, gRPC, or Consul. Those
> are adapters behind abstract interfaces. This means I can unit-test the
> entire domain with in-memory fakes, swap infrastructure without touching
> business logic, and onboard juniors who only need to understand the domain."

### 2. "How does this library help the team?"
> "Instead of each team learning how to configure structlog + prometheus_client
> + Keycloak + psycopg2 individually, this library provides one-line setup.
> Standards propagate through code, not documentation."

### 3. "How does this relate to 5S?"
> - **Sort**: Clear separation — domain, ports, adapters. No mixed concerns.
> - **Set in Order**: Every service follows the same directory layout.
> - **Shine**: CI gates enforce quality — linting, type checking, coverage.
> - **Standardize**: Cookiecutter template uses this library by default.
> - **Sustain**: Architecture tests prevent layer violations.

### 4. "How do you test this?"
> "Domain logic is tested with in-memory adapters — no database, no network.
> Adapters are tested individually with testcontainers (real PostgreSQL).
> Integration tests verify the wiring. This gives us a fast, reliable,
> three-layer test pyramid."

---

## Project Structure (5S: Set in Order)

```
dat_service_lib/
├── README.md                          ← You are here
├── requirements.txt                   ← Pinned dependencies
├── setup.py                           ← Package installation
├── dat_service_lib/
│   ├── __init__.py                    ← Public API: from dat_service_lib import ...
│   ├── core/
│   │   ├── domain/
│   │   │   ├── __init__.py
│   │   │   ├── models.py             ← Dataclasses (SensorReading, etc.)
│   │   │   ├── exceptions.py         ← Domain exception hierarchy
│   │   │   └── validators.py         ← Pure validation functions
│   │   ├── ports/
│   │   │   ├── __init__.py
│   │   │   └── interfaces.py         ← ABCs: ReadingRepository, AlertNotifier, etc.
│   │   └── services/
│   │       ├── __init__.py
│   │       └── sensor_service.py     ← Business logic orchestration
│   ├── adapters/
│   │   ├── persistence/
│   │   │   ├── __init__.py
│   │   │   ├── postgres_repo.py      ← PostgreSQL adapter
│   │   │   └── in_memory_repo.py     ← In-memory adapter (for tests)
│   │   ├── messaging/
│   │   │   ├── __init__.py
│   │   │   └── alert_adapters.py     ← Slack, Log, Email alert adapters
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   └── keycloak_auth.py      ← JWT validation adapter
│   │   ├── observability/
│   │   │   ├── __init__.py
│   │   │   ├── logging.py            ← Structured logging setup
│   │   │   └── metrics.py            ← Prometheus metrics
│   │   └── config/
│   │       ├── __init__.py
│   │       └── settings.py           ← Env-based config loading
│   └── utils/
│       ├── __init__.py
│       ├── retry.py                  ← Retry decorator with backoff
│       └── circuit_breaker.py        ← Circuit breaker pattern
├── tests/
│   ├── conftest.py                   ← Shared fixtures
│   ├── unit/
│   │   ├── test_models.py
│   │   ├── test_validators.py
│   │   ├── test_sensor_service.py    ← Tests domain with in-memory adapters
│   │   └── test_circuit_breaker.py
│   └── integration/
│       └── test_postgres_repo.py     ← Tests real DB (skip if no DB)
├── examples/
│   ├── __init__.py
│   └── run_demo.py                   ← Full working demo
└── proto/
    └── sensor_service.proto          ← gRPC schema (reference)
```
>>>>>>> Added initial files
