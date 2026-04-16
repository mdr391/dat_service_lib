"""
Configuration — Environment-based config loading.

"""
import os
from dataclasses import dataclass


@dataclass
class ServiceConfig:
    """Central configuration — loaded once at startup."""

    # Service identity
    service_name: str = "dat-service"
    service_version: str = "1.0.0"

    # gRPC
    grpc_port: int = 50051
    grpc_max_workers: int = 10

    # Database
    db_dsn: str = "postgresql://localhost:5432/dat"
    db_pool_min: int = 2
    db_pool_max: int = 10

    # Observability
    log_level: str = "INFO"
    log_json: bool = True
    metrics_port: int = 9090

    # Consul
    consul_host: str = "localhost"
    consul_port: int = 8500

    # Auth
    keycloak_url: str = "http://localhost:8080/auth"
    keycloak_realm: str = "dat"

    # Anomaly detection
    anomaly_z_threshold: float = 2.0

    @classmethod
    def from_env(cls) -> "ServiceConfig":
        """
        Load config from environment variables.
        Every field can be overridden by an env var:
        SERVICE_NAME, GRPC_PORT, DB_DSN, LOG_LEVEL, etc.
        """
        return cls(
            service_name=os.getenv("SERVICE_NAME", cls.service_name),
            service_version=os.getenv("SERVICE_VERSION", cls.service_version),
            grpc_port=int(os.getenv("GRPC_PORT", str(cls.grpc_port))),
            grpc_max_workers=int(os.getenv("GRPC_MAX_WORKERS", str(cls.grpc_max_workers))),
            db_dsn=os.getenv("DB_DSN", cls.db_dsn),
            db_pool_min=int(os.getenv("DB_POOL_MIN", str(cls.db_pool_min))),
            db_pool_max=int(os.getenv("DB_POOL_MAX", str(cls.db_pool_max))),
            log_level=os.getenv("LOG_LEVEL", cls.log_level),
            log_json=os.getenv("LOG_JSON", "true").lower() == "true",
            metrics_port=int(os.getenv("METRICS_PORT", str(cls.metrics_port))),
            consul_host=os.getenv("CONSUL_HOST", cls.consul_host),
            consul_port=int(os.getenv("CONSUL_PORT", str(cls.consul_port))),
            keycloak_url=os.getenv("KEYCLOAK_URL", cls.keycloak_url),
            keycloak_realm=os.getenv("KEYCLOAK_REALM", cls.keycloak_realm),
            anomaly_z_threshold=float(os.getenv("ANOMALY_Z_THRESHOLD", str(cls.anomaly_z_threshold))),
        )
