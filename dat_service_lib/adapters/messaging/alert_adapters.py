"""
Alert Adapters — Multiple implementations of the AlertNotifier port.

INTERVIEW POINT: "Strategy Pattern in action — the SensorService
calls alerter.send_alert() without knowing if it goes to Slack,
email, a log file, or all three. We can swap or combine alerters
without touching the service layer."
"""
import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any, List

from ...core.ports.interfaces import AlertNotifier

logger = logging.getLogger(__name__)


class LogAlertNotifier(AlertNotifier):
    """
    Logs alerts to structured logging — used in dev/test.
    No external dependencies needed.
    """

    def send_alert(
        self,
        sensor_id: str,
        message: str,
        severity: str = "warning",
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        logger.warning(
            "ALERT",
            extra={
                "sensor_id": sensor_id,
                "alert_message": message,
                "severity": severity,
                "context": context or {},
                "alert_type": "log",
            }
        )
        return True


class SlackAlertNotifier(AlertNotifier):
    """
    Sends alerts to a Slack webhook.
    In production, would use requests library.
    """

    def __init__(self, webhook_url: str, channel: str = "#dat-alerts"):
        self._webhook_url = webhook_url
        self._channel = channel

    def send_alert(
        self,
        sensor_id: str,
        message: str,
        severity: str = "warning",
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        severity_emoji = {
            "info": "ℹ️",
            "warning": "⚠️",
            "critical": "🔴",
        }
        emoji = severity_emoji.get(severity, "⚠️")

        payload = {
            "channel": self._channel,
            "text": f"{emoji} *[{severity.upper()}]* Sensor `{sensor_id}`\n{message}",
            "attachments": [{
                "color": "#ff5c5c" if severity == "critical" else "#ffb830",
                "fields": [
                    {"title": "Sensor", "value": sensor_id, "short": True},
                    {"title": "Severity", "value": severity, "short": True},
                    {"title": "Time", "value": datetime.utcnow().isoformat(), "short": True},
                ],
            }],
        }

        # In production: requests.post(self._webhook_url, json=payload)
        logger.info("slack_alert_sent", extra={
            "sensor_id": sensor_id,
            "channel": self._channel,
            "severity": severity,
        })
        return True


class CompositeAlertNotifier(AlertNotifier):
    """
    Composite Pattern — sends alerts through multiple notifiers.

    INTERVIEW POINT: "I use the composite pattern to fan out alerts
    to multiple channels. An anomaly alert goes to Slack AND the
    log file AND the metrics counter simultaneously."
    """

    def __init__(self, notifiers: List[AlertNotifier]):
        self._notifiers = notifiers

    def send_alert(
        self,
        sensor_id: str,
        message: str,
        severity: str = "warning",
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        results = []
        for notifier in self._notifiers:
            try:
                result = notifier.send_alert(sensor_id, message, severity, context)
                results.append(result)
            except Exception as e:
                logger.error(f"alert_notifier_failed: {type(notifier).__name__}: {e}")
                results.append(False)
        return any(results)  # True if at least one succeeded
