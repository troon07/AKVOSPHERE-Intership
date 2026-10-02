import logging
from datetime import UTC, datetime
from typing import Any

from app.config.automation_settings import OFFLINE_DETECTION
from app.database.queries import (
    create_alert,
    get_all_latest_machine_states,
    has_unresolved_alert,
    resolve_alert,
    update_unresolved_alert,
)
from app.services.automation_execution_logger import log_automation_execution

logger = logging.getLogger(__name__)

SEVERITY_RANK = {
    "warning": 1,
    "high": 2,
    "critical": 3,
}


def _parse_esp_log_at(value: Any) -> datetime | None:
    """Parse a Supabase timestamp value into a timezone-aware UTC datetime."""

    if isinstance(value, datetime):
        timestamp = value
    elif isinstance(value, str):
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            logger.warning(
                "event=invalid_sensor_timestamp esp_log_at=%s status=skipped",
                value,
            )
            return None
    else:
        logger.warning(
            "event=unsupported_sensor_timestamp esp_log_at=%r status=skipped",
            value,
        )
        return None

    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)

    return timestamp.astimezone(UTC)


def _get_offline_severity(offline_duration_seconds: int) -> tuple[str, str]:
    """Return deterministic severity and reason for offline duration."""

    if offline_duration_seconds >= OFFLINE_DETECTION.offline_critical_seconds:
        return "critical", "prolonged machine offline duration"

    if offline_duration_seconds >= OFFLINE_DETECTION.offline_high_seconds:
        return "high", "moderate machine offline interruption"

    return "warning", "transient machine connectivity instability"


def _should_escalate(current_severity: str | None, target_severity: str) -> bool:
    return SEVERITY_RANK.get(target_severity, 0) > SEVERITY_RANK.get(
        current_severity or "",
        0,
    )


def run_offline_detection() -> bool:
    """Detect offline machines and resolve offline alerts after recovery."""

    started_at = datetime.now(UTC)
    analyzed_machine_count = 0
    detection_count = 0
    severity_distribution = {
        "warning": 0,
        "high": 0,
        "critical": 0,
    }

    try:
        machine_states = get_all_latest_machine_states()
        now = datetime.now(UTC)

        for state in machine_states:
            machine_id = state.get("machine_id")
            esp_log_at = _parse_esp_log_at(state.get("esp_log_at"))

            if not machine_id:
                logger.warning(
                    "event=sensor_state_missing_machine_id state=%s status=skipped",
                    state,
                )
                continue

            if esp_log_at is None:
                logger.warning(
                    "event=offline_check_skipped machine_id=%s reason=missing_timestamp status=skipped",
                    machine_id,
                )
                continue

            analyzed_machine_count += 1
            offline_duration = now - esp_log_at
            offline_duration_seconds = int(offline_duration.total_seconds())

            if offline_duration_seconds < OFFLINE_DETECTION.offline_warning_seconds:

                if has_unresolved_alert(
                    machine_id=machine_id,
                    alert_type=OFFLINE_DETECTION.alert_type,
                ):

                    resolved_alert = resolve_alert(
                        machine_id=machine_id,
                        alert_type=OFFLINE_DETECTION.alert_type,
                    )

                    if resolved_alert:
                        logger.info(
                            "event=machine_offline_detected_resolved machine_id=%s alert_type=%s status=resolved",
                            machine_id,
                            OFFLINE_DETECTION.alert_type,
                        )

                continue

            severity, severity_reason = _get_offline_severity(
                offline_duration_seconds
            )
            severity_distribution[severity] += 1
            offline_duration_minutes = round(offline_duration_seconds / 60, 2)

            logger.warning(
                "event=machine_offline_detected machine_id=%s alert_type=%s severity=%s offline_duration_seconds=%s offline_duration_minutes=%s severity_reason=%s last_seen_at=%s status=alerting",
                machine_id,
                OFFLINE_DETECTION.alert_type,
                severity,
                offline_duration_seconds,
                offline_duration_minutes,
                severity_reason,
                esp_log_at.isoformat(),
            )
            detection_count += 1

            alert = create_alert(
                machine_id=machine_id,
                alert_type=OFFLINE_DETECTION.alert_type,
                severity=severity,
                message="Machine is offline. No recent telemetry received.",
                metadata={
                    "offline_duration_seconds": offline_duration_seconds,
                    "offline_duration_minutes": offline_duration_minutes,
                    "severity_reason": severity_reason,
                    "last_seen_at": esp_log_at.isoformat(),
                },
            )
            if alert and _should_escalate(alert.get("severity"), severity):
                update_unresolved_alert(
                    machine_id=machine_id,
                    alert_type=OFFLINE_DETECTION.alert_type,
                    updates={
                        "severity": severity,
                        "metadata": {
                            "offline_duration_seconds": offline_duration_seconds,
                            "offline_duration_minutes": offline_duration_minutes,
                            "severity_reason": severity_reason,
                            "last_seen_at": esp_log_at.isoformat(),
                        },
                    },
                )
                logger.warning(
                    "event=machine_offline_detected_severity_escalated machine_id=%s alert_type=%s previous_severity=%s new_severity=%s offline_duration_seconds=%s status=updated",
                    machine_id,
                    OFFLINE_DETECTION.alert_type,
                    alert.get("severity"),
                    severity,
                    offline_duration_seconds,
                )

        completed_at = datetime.now(UTC)
        log_automation_execution(
            automation_name=OFFLINE_DETECTION.automation_id,
            started_at=started_at,
            completed_at=completed_at,
            execution_duration_ms=round(
                (completed_at - started_at).total_seconds() * 1000,
                2,
            ),
            analyzed_machine_count=analyzed_machine_count,
            detection_count=detection_count,
            status="success",
        )
        logger.info(
            "event=offline_detection_severity_distribution warning=%s high=%s critical=%s status=success",
            severity_distribution["warning"],
            severity_distribution["high"],
            severity_distribution["critical"],
        )
        return True
    except Exception as exc:
        completed_at = datetime.now(UTC)
        log_automation_execution(
            automation_name=OFFLINE_DETECTION.automation_id,
            started_at=started_at,
            completed_at=completed_at,
            execution_duration_ms=round(
                (completed_at - started_at).total_seconds() * 1000,
                2,
            ),
            analyzed_machine_count=analyzed_machine_count,
            detection_count=detection_count,
            status="failed",
            error_message=str(exc),
        )
        logger.exception(
            "event=automation_failed automation_id=%s status=failed",
            OFFLINE_DETECTION.automation_id,
        )
        return False
