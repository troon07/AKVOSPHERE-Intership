"""
Shared mutable state and locking mechanism for the AKVO AWG system.
"""
import threading
from dataclasses import dataclass

lock = threading.Lock()

@dataclass
class SystemState:
    pulse_count: int = 0
    pipe_temp_c: float = 0.0
    ambient_temp_c: float = 0.0
    humidity_pct: float = 0.0
    flow_rate_lmin: float = 0.0
    total_volume_l: float = 0.0
    sht45_ok: bool = False
    ds18b20_ok: bool = False

    # ── AWG state-machine ──────────────────────────────────────
    # Modes: STARTUP → FAN_ONLY → AWG_RUN ↔ PUMPING → TANK_FULL → FAN_ONLY …
    awg_mode: str = "STARTUP"
    mode_entered_at: float = 0.0   # time.monotonic() when current mode began
    pump_started_at: float = 0.0   # time.monotonic() when PUMPING mode began

state = SystemState()
