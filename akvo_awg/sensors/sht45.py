"""
Initialization and reading logic for the SHT45 humidity/temperature sensor.
"""
import board
import busio
import adafruit_sht4x
from akvo_awg.logger import log
from akvo_awg.state import state

def init_sht45():
    """Return SHT4x sensor object or None on failure."""
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        sensor = adafruit_sht4x.SHT4x(i2c)
        sensor.mode = adafruit_sht4x.Mode.NOHEAT_HIGHPRECISION
        log.info("[SHT45]   Initialized at 0x44 — OK")
        return sensor
    except Exception as e:
        log.error(f"[SHT45]   Init failed: {e}")
        log.error("[SHT45]   Causes: wrong VCC, swapped SDA/SCL, missing pull-ups")
        return None

def read_sht45(sensor):
    """
    Read loop logic for SHT45 with retry on failure.
    Updates the shared state with the new readings.
    Returns the sensor object (which could be newly re-initialized) or None.
    """
    # SHT45 — retry init if it failed at boot
    if not state.sht45_ok:
        sensor = init_sht45()
        state.sht45_ok = (sensor is not None)
        if state.sht45_ok:
            log.info("[SHT45]   Reconnected OK")

    if state.sht45_ok:
        try:
            temperature, relative_humidity = sensor.measurements
            if 0.0 <= relative_humidity <= 100.0:
                state.ambient_temp_c = temperature
                state.humidity_pct   = relative_humidity
            else:
                log.warning("[SHT45]   WARN: Out-of-range reading (NaN or >100%)")
        except Exception as e:
            log.warning(f"[SHT45]   Read error: {e}")
            state.sht45_ok = False   # will retry next cycle

    return sensor
