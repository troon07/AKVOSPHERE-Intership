"""
Flow rate calculation and volume accumulator logic.
"""
from akvo_awg.state import state, lock
from akvo_awg.config import PULSES_PER_LITRE
from akvo_awg.logger import log

def calculate_flow():
    """
    Flow rate calc, total volume accumulator using pulse_count with threading.Lock.
    """
    with lock:
        pulses = state.pulse_count
        state.pulse_count = 0

    log.debug(f"[FLOW]    Pulses this second: {pulses}")

    litres_this_cycle = pulses / PULSES_PER_LITRE
    state.flow_rate_lmin = litres_this_cycle * 60.0
    state.total_volume_l += litres_this_cycle
