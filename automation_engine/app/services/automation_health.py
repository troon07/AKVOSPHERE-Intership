import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.config.automation_settings import (
    COMPRESSOR_RAPID_CYCLING,
    CONTINUOUS_PUMP_RUNTIME_DETECTION,
    FAN_COMPRESSOR_SEQUENCE,
    OFFLINE_DETECTION,
    OPERATIONAL_INTEGRITY_VALIDATION,
    SENSOR_FREEZE_DETECTION,
)
from app.database.queries import (
    get_alerts_since,
    get_automation_execution_logs_since,
    get_unresolved_alert_summaries,
)

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_HOURS = 24

AUTOMATION_ALERT_TYPES = {
    OFFLINE_DETECTION.automation_id: {OFFLINE_DETECTION.alert_type},
    COMPRESSOR_RAPID_CYCLING.automation_id: {COMPRESSOR_RAPID_CYCLING.alert_type},
    FAN_COMPRESSOR_SEQUENCE.automation_id: {
        FAN_COMPRESSOR_SEQUENCE.startup_alert_type,
        FAN_COMPRESSOR_SEQUENCE.runtime_alert_type,
        FAN_COMPRESSOR_SEQUENCE.shutdown_alert_type,
    },
    OPERATIONAL_INTEGRITY_VALIDATION.automation_id: {
        "validation_invalid_humidity",
        "validation_invalid_voltage",
        "validation_invalid_current",
        "validation_invalid_watts",
        "validation_power_state_mismatch",
        "validation_pump_tank_conflict",
    },
    SENSOR_FREEZE_DETECTION.automation_id: {SENSOR_FREEZE_DETECTION.alert_type},
    CONTINUOUS_PUMP_RUNTIME_DETECTION.automation_id: {
        CONTINUOUS_PUMP_RUNTIME_DETECTION.alert_type
    },
}


def _empty_summary() -> dict[str, Any]:
    return {
        "executions": 0,
        "detections": 0,
        "failures": 0,
        "avg_duration_ms": 0,
        "max_duration_ms": 0,
        "success_rate": 0.0,
        "unresolved_alerts": 0,
        "critical_alerts": 0,
        "high_alerts": 0,
    }


def _automation_for_alert_type(alert_type: str) -> str | None:
    for automation_id, alert_types in AUTOMATION_ALERT_TYPES.items():
        if alert_type in alert_types:
            return automation_id
    return None


def build_automation_health_summary(
    window_hours: int = DEFAULT_WINDOW_HOURS,
) -> dict[str, Any]:
    """Build a bounded operational health summary for automation behavior."""

    since = datetime.now(UTC) - timedelta(hours=window_hours)
    execution_logs = get_automation_execution_logs_since(since)
    recent_alerts = get_alerts_since(since)
    unresolved_alerts = get_unresolved_alert_summaries()

    summaries = {
        automation_id: _empty_summary()
        for automation_id in AUTOMATION_ALERT_TYPES
    }
    duration_totals: dict[str, int] = {
        automation_id: 0 for automation_id in AUTOMATION_ALERT_TYPES
    }

    for log_row in execution_logs:
        automation_name = log_row.get("automation_name")
        if not automation_name:
            continue

        automation_name = str(automation_name)
        summary = summaries.setdefault(automation_name, _empty_summary())
        duration_totals.setdefault(automation_name, 0)

        duration_ms = int(log_row.get("execution_duration_ms") or 0)
        detections = int(log_row.get("detection_count") or 0)
        status = str(log_row.get("status") or "").lower()

        summary["executions"] += 1
        summary["detections"] += detections
        summary["max_duration_ms"] = max(summary["max_duration_ms"], duration_ms)
        duration_totals[automation_name] += duration_ms
        if status != "success":
            summary["failures"] += 1

    for automation_name, summary in summaries.items():
        executions = summary["executions"]
        if executions:
            summary["avg_duration_ms"] = round(
                duration_totals[automation_name] / executions
            )
            summary["success_rate"] = round(
                ((executions - summary["failures"]) / executions) * 100,
                2,
            )

    for alert_row in recent_alerts:
        automation_name = _automation_for_alert_type(str(alert_row.get("alert_type")))
        if not automation_name:
            continue

        summary = summaries.setdefault(automation_name, _empty_summary())
        severity = str(alert_row.get("severity") or "").lower()
        if severity == "critical":
            summary["critical_alerts"] += 1
        elif severity == "high":
            summary["high_alerts"] += 1

    for alert_row in unresolved_alerts:
        automation_name = _automation_for_alert_type(str(alert_row.get("alert_type")))
        if not automation_name:
            continue

        summary = summaries.setdefault(automation_name, _empty_summary())
        summary["unresolved_alerts"] += 1

    logger.debug(
        "event=automation_health_summary_built window_hours=%s automation_count=%s status=success",
        window_hours,
        len(summaries),
    )

    return {
        "status": "ok",
        "window_hours": window_hours,
        "automations": summaries,
    }
