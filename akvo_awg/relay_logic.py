"""
AWG state-machine relay logic.

update_awg_state(now) is called every 100 ms from the main loop.
It checks the current awg_mode, reads float sensors and elapsed
timers, then transitions to the next mode when conditions are met.

Rules:
  - No time.sleep() — all timing is elapsed-time via monotonic clock.
  - No asyncio, no new threads, no libraries beyond what already exists.
  - Float reads happen ONLY here — never in main.py directly.
  - When no transition is needed the function returns immediately
    with zero side-effects (safe to call every 100 ms).
"""
from akvo_awg.config import (
    FAN_PREHEAT_DURATION,
    TANK_SLEEP_DURATION,
    PUMP_RUN_TIMEOUT,
)
from akvo_awg.state import state
from akvo_awg.gpio_setup import set_relays, read_floats
from akvo_awg.logger import log

# ---------------------------------------------------------------------------
# Relay truth-table per mode
#                      fan    compressor  pump
_RELAY_MAP = {
    "STARTUP":    (False, False,      False),
    "FAN_ONLY":   (True,  False,      False),
    "AWG_RUN":    (True,  True,       False),
    "PUMPING":    (True,  True,       True),
    "TANK_FULL":  (False, False,      False),
}
# ---------------------------------------------------------------------------


def _enter_mode(new_mode: str, now: float, old_mode: str) -> None:
    """Apply relay outputs, update state, and log the transition."""
    fan, compressor, pump = _RELAY_MAP[new_mode]
    set_relays(fan, compressor, pump)
    log.info(f"[AWG] {old_mode} → {new_mode}  "
             f"(fan={'ON' if fan else 'OFF'}  "
             f"compressor={'ON' if compressor else 'OFF'}  "
             f"pump={'ON' if pump else 'OFF'})")
    state.awg_mode = new_mode
    state.mode_entered_at = now


def update_awg_state(now: float) -> None:
    """Evaluate the current AWG mode and transition when conditions are met.

    Called every 100 ms from the main loop.  Returns immediately with no
    side-effects when the current mode's exit condition is not yet satisfied.

    Args:
        now: Current value of time.monotonic() passed in from the main loop.
    """
    mode = state.awg_mode

    # ── STARTUP ────────────────────────────────────────────────────────────
    # Immediately kick the fan on.  STARTUP only exists so that the very
    # first call after init sets mode_entered_at correctly.
    if mode == "STARTUP":
        _enter_mode("FAN_ONLY", now, mode)

    # ── FAN_ONLY ───────────────────────────────────────────────────────────
    # Fan runs alone for FAN_PREHEAT_DURATION seconds, then the compressor
    # joins to begin the AWG collection cycle.
    elif mode == "FAN_ONLY":
        if (now - state.mode_entered_at) >= FAN_PREHEAT_DURATION:
            _enter_mode("AWG_RUN", now, mode)

    # ── AWG_RUN ────────────────────────────────────────────────────────────
    # Fan + compressor running; water condenses into the internal sink.
    # Priority: check tank float first (overrides sink float if both trigger).
    elif mode == "AWG_RUN":
        sink, tank = read_floats()
        if tank:
            # External tank is full — sleep immediately.
            _enter_mode("TANK_FULL", now, mode)
        elif sink:
            # Internal sink has water — start pumping it to the tank.
            state.pump_started_at = now
            _enter_mode("PUMPING", now, mode)

    # ── PUMPING ────────────────────────────────────────────────────────────
    # Fan + compressor + pump all ON.  Pump drains the internal sink into
    # the external tank.
    elif mode == "PUMPING":
        sink, tank = read_floats()
        if tank:
            # Tank filled while pumping — stop everything and sleep.
            _enter_mode("TANK_FULL", now, mode)
        elif not sink:
            # Sink drained successfully — turn pump off and resume collecting.
            _enter_mode("AWG_RUN", now, mode)
        elif (now - state.pump_started_at) >= PUMP_RUN_TIMEOUT:
            # Safety fallback: pump has been running too long without draining.
            # The sink float may be stuck.  Back off to AWG_RUN to avoid
            # running the pump dry or causing overflow.
            log.warning(
                "[AWG] Pump timeout — sink float may be stuck. "
                f"Pump ran for {PUMP_RUN_TIMEOUT}s without sink clearing. "
                "Backing off to AWG_RUN."
            )
            _enter_mode("AWG_RUN", now, mode)

    # ── TANK_FULL ──────────────────────────────────────────────────────────
    # Everything OFF.  Machine sleeps for TANK_SLEEP_DURATION, then restarts
    # the full cycle from the fan-preheat step.
    elif mode == "TANK_FULL":
        if (now - state.mode_entered_at) >= TANK_SLEEP_DURATION:
            _enter_mode("FAN_ONLY", now, mode)
