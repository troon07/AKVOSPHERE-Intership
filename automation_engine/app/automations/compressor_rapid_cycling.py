import logging
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from app.config.automation_settings import COMPRESSOR_RAPID_CYCLING
from app.database.queries import (
    create_alert,
    get_sensor_data_since,
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


def _normalize_compressor_status(value: Any) -> str | None:
    """Normalize compressor status values for transition detection."""

    if value is None:
        return None

    if isinstance(value, bool):
        return "on" if value else "off"

    return str(value).strip().lower()


def _count_transitions(rows: list[dict[str, Any]]) -> int:
    """Count compressor status transitions in timestamp-ordered sensor rows."""

    transitions = 0
    previous_status: str | None = None

    for row in rows:
        current_status = _normalize_compressor_status(row.get("compressor_status"))
        if current_status is None:
            continue

        if previous_status is not None and current_status != previous_status:
            transitions += 1

        previous_status = current_status

    return transitions


def _get_rapid_cycling_severity(transitions: int) -> tuple[str, str]:
    """Return deterministic severity and reason for transition intensity."""

    if transitions >= COMPRESSOR_RAPID_CYCLING.rapid_cycling_critical_threshold:
        return "critical", "excessive compressor cycling frequency"

    if transitions >= COMPRESSOR_RAPID_CYCLING.rapid_cycling_high_threshold:
        return "high", "high compressor cycling frequency"

    return "warning", "compressor cycling frequency exceeded warning threshold"


def _should_escalate(current_severity: str | None, target_severity: str) -> bool:
    return SEVERITY_RANK.get(target_severity, 0) > SEVERITY_RANK.get(
        current_severity or "",
        0,
    )


def run_compressor_rapid_cycling_detection() -> bool:
    """Detect rapid cycling and resolve alerts after compressor behavior stabilizes."""

    started_at = datetime.now(UTC)
    analyzed_machine_count = 0
    detection_count = 0
    severity_distribution = {
        "warning": 0,
        "high": 0,
        "critical": 0,
    }

    try:
        since = datetime.now(UTC) - COMPRESSOR_RAPID_CYCLING.lookback_window
        sensor_rows = get_sensor_data_since(since)
        rows_by_machine: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for row in sensor_rows:
            machine_id = row.get("machine_id")
            if not machine_id:
                logger.warning(
                    "event=sensor_row_missing_machine_id row=%s status=skipped",
                    row,
                )
                continue

            rows_by_machine[str(machine_id)].append(row)

        for machine_id, machine_rows in rows_by_machine.items():
            analyzed_machine_count += 1
            transitions = _count_transitions(machine_rows)
            if transitions < COMPRESSOR_RAPID_CYCLING.rapid_cycling_warning_threshold:
                if has_unresolved_alert(
                    machine_id=machine_id,
                    alert_type=COMPRESSOR_RAPID_CYCLING.alert_type,
                ):
                    resolved_alert = resolve_alert(
                        machine_id=machine_id,
                        alert_type=COMPRESSOR_RAPID_CYCLING.alert_type,
                    )
                    if resolved_alert:
                        logger.info(
                            "event=compressor_cycling_stabilized machine_id=%s alert_type=%s transitions=%s status=resolved",
                            machine_id,
                            COMPRESSOR_RAPID_CYCLING.alert_type,
                            transitions,
                        )

                continue

            severity, severity_reason = _get_rapid_cycling_severity(transitions)
            severity_distribution[severity] += 1
            logger.warning(
                "event=compressor_rapid_cycling_detected machine_id=%s alert_type=%s transitions=%s severity=%s severity_reason=%s threshold=%s status=alerting",
                machine_id,
                COMPRESSOR_RAPID_CYCLING.alert_type,
                transitions,
                severity,
                severity_reason,
                COMPRESSOR_RAPID_CYCLING.rapid_cycling_warning_threshold,
            )
            detection_count += 1
            alert = create_alert(
                machine_id=machine_id,
                alert_type=COMPRESSOR_RAPID_CYCLING.alert_type,
                severity=severity,
                message="Compressor rapid cycling detected in the last 10 minutes.",
                metadata={
                    "lookback_minutes": int(
                        COMPRESSOR_RAPID_CYCLING.lookback_window.total_seconds() / 60
                    ),
                    "transition_count": transitions,
                    "severity_reason": severity_reason,
                },
            )
            if alert and _should_escalate(alert.get("severity"), severity):
                update_unresolved_alert(
                    machine_id=machine_id,
                    alert_type=COMPRESSOR_RAPID_CYCLING.alert_type,
                    updates={
                        "severity": severity,
                        "metadata": {
                            "lookback_minutes": int(
                                COMPRESSOR_RAPID_CYCLING.lookback_window.total_seconds()
                                / 60
                            ),
                            "transition_count": transitions,
                            "severity_reason": severity_reason,
                        },
                    },
                )
                logger.warning(
                    "event=compressor_rapid_cycling_severity_escalated machine_id=%s alert_type=%s previous_severity=%s new_severity=%s transitions=%s status=updated",
                    machine_id,
                    COMPRESSOR_RAPID_CYCLING.alert_type,
                    alert.get("severity"),
                    severity,
                    transitions,
                )
        completed_at = datetime.now(UTC)
        log_automation_execution(
            automation_name=COMPRESSOR_RAPID_CYCLING.automation_id,
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
            "event=compressor_rapid_cycling_severity_distribution warning=%s high=%s critical=%s status=success",
            severity_distribution["warning"],
            severity_distribution["high"],
            severity_distribution["critical"],
        )
        return True
    except Exception as exc:
        completed_at = datetime.now(UTC)
        log_automation_execution(
            automation_name=COMPRESSOR_RAPID_CYCLING.automation_id,
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
            COMPRESSOR_RAPID_CYCLING.automation_id,
        )
        return False
