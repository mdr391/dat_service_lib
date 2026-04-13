"""
PostgreSQL Repository Adapter — Production persistence.

INTERVIEW POINT: "This adapter implements the same interface as
InMemoryReadingRepo. In production, the service uses this. In tests,
it uses InMemoryReadingRepo. The SensorService doesn't change at all.
That's the power of hexagonal architecture + dependency injection."
"""
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from ...core.ports.interfaces import ReadingRepository
from ...core.domain.models import (
    SensorReading, SensorStats, SensorUnit, ReadingStatus,
)
from ...core.domain.exceptions import RepositoryError

logger = logging.getLogger(__name__)


class PostgresReadingRepo(ReadingRepository):
    """
    PostgreSQL implementation of ReadingRepository.

    Uses psycopg2 connection pool for production-grade performance.
    All SQL is parameterized — never string interpolation (SQL injection prevention).
    """

    def __init__(self, connection_pool) -> None:
        """
        Args:
            connection_pool: psycopg2 connection pool or compatible.
        """
        self._pool = connection_pool

    @contextmanager
    def _get_conn(self):
        """Get a connection from the pool with automatic cleanup."""
        conn = self._pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    def save(self, reading: SensorReading) -> None:
        """Insert a single reading using parameterized query."""
        sql = """
            INSERT INTO sensor_readings
                (sensor_id, value, unit, recorded_at, status, correlation_id, tags, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        try:
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (
                        reading.sensor_id,
                        reading.value,
                        reading.unit.value,
                        reading.timestamp,
                        reading.status.value,
                        reading.correlation_id,
                        reading.tags,       # PostgreSQL array
                        str(reading.metadata),  # JSONB
                    ))
        except Exception as e:
            logger.error("db_save_failed", extra={
                "sensor_id": reading.sensor_id, "error": str(e)
            })
            raise RepositoryError(f"Failed to save reading: {e}") from e

    def save_batch(self, readings: List[SensorReading]) -> int:
        """
        Batch insert using execute_values for performance.

        INTERVIEW POINT: "I use execute_values for batch inserts —
        it's 10x faster than individual INSERT statements because
        it reduces network round-trips to one."
        """
        if not readings:
            return 0

        sql = """
            INSERT INTO sensor_readings
                (sensor_id, value, unit, recorded_at, status, correlation_id)
            VALUES %s
        """
        values = [
            (r.sensor_id, r.value, r.unit.value,
             r.timestamp, r.status.value, r.correlation_id)
            for r in readings
        ]

        try:
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    # psycopg2.extras.execute_values for batch performance
                    from psycopg2.extras import execute_values
                    execute_values(cur, sql, values)
                    return len(values)
        except Exception as e:
            raise RepositoryError(f"Batch save failed: {e}") from e

    def get_by_sensor(
        self,
        sensor_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[SensorReading]:
        """Query with parameterized SQL — never string interpolation."""
        conditions = ["sensor_id = %s"]
        params: list = [sensor_id]

        if start:
            conditions.append("recorded_at >= %s")
            params.append(start)
        if end:
            conditions.append("recorded_at <= %s")
            params.append(end)

        where = " AND ".join(conditions)
        sql = f"""
            SELECT sensor_id, value, unit, recorded_at, status, correlation_id
            FROM sensor_readings
            WHERE {where}
            ORDER BY recorded_at DESC
            LIMIT %s
        """
        params.append(limit)

        try:
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    rows = cur.fetchall()
                    return [self._row_to_reading(row) for row in rows]
        except Exception as e:
            raise RepositoryError(f"Query failed: {e}") from e

    def get_latest(self, sensor_id: str) -> Optional[SensorReading]:
        """Get most recent reading using DISTINCT ON (PostgreSQL-specific)."""
        sql = """
            SELECT sensor_id, value, unit, recorded_at, status, correlation_id
            FROM sensor_readings
            WHERE sensor_id = %s
            ORDER BY recorded_at DESC
            LIMIT 1
        """
        try:
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (sensor_id,))
                    row = cur.fetchone()
                    return self._row_to_reading(row) if row else None
        except Exception as e:
            raise RepositoryError(f"get_latest failed: {e}") from e

    def get_stats(
        self,
        sensor_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> Optional[SensorStats]:
        """Compute stats using SQL aggregation — efficient on large datasets."""
        conditions = ["sensor_id = %s"]
        params: list = [sensor_id]

        if start:
            conditions.append("recorded_at >= %s")
            params.append(start)
        if end:
            conditions.append("recorded_at <= %s")
            params.append(end)

        where = " AND ".join(conditions)
        sql = f"""
            SELECT
                COUNT(*),
                ROUND(AVG(value)::numeric, 4),
                ROUND(STDDEV(value)::numeric, 4),
                MIN(value),
                MAX(value),
                COUNT(*) FILTER (WHERE status = 'anomaly'),
                MIN(recorded_at),
                MAX(recorded_at)
            FROM sensor_readings
            WHERE {where}
        """

        try:
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    row = cur.fetchone()
                    if not row or row[0] == 0:
                        return None
                    return SensorStats(
                        sensor_id=sensor_id,
                        count=row[0],
                        mean=float(row[1]) if row[1] else 0.0,
                        std_dev=float(row[2]) if row[2] else 0.0,
                        min_value=float(row[3]),
                        max_value=float(row[4]),
                        anomaly_count=row[5],
                        period_start=row[6],
                        period_end=row[7],
                    )
        except Exception as e:
            raise RepositoryError(f"get_stats failed: {e}") from e

    @staticmethod
    def _row_to_reading(row) -> SensorReading:
        """Map a database row to a domain model."""
        return SensorReading(
            sensor_id=row[0],
            value=float(row[1]),
            unit=SensorUnit(row[2]),
            timestamp=row[3],
            status=ReadingStatus(row[4]),
            correlation_id=row[5] or "",
        )
