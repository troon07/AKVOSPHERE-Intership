"""
GPIO initialization, ISR for flow sensor, and relay control.
"""
import RPi.GPIO as GPIO
from akvo_awg.config import (
    FLOW_PIN,
    RELAY_FAN_PIN, RELAY_COMPRESSOR_PIN, RELAY_PUMP_PIN,
    FLOAT_SINK_PIN, FLOAT_TANK_PIN,
)
from akvo_awg.state import state, lock
from akvo_awg.logger import log

def flow_pulse_isr(channel):
    """Increment pulse counter on each falling edge from flow sensor."""
    with lock:
        state.pulse_count += 1

def init_gpio():
    """Initialize GPIO pins and configure interrupts."""
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    # Relay outputs — all start LOW (OFF) so no component is energised on boot
    GPIO.setup(RELAY_FAN_PIN,        GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(RELAY_COMPRESSOR_PIN, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(RELAY_PUMP_PIN,       GPIO.OUT, initial=GPIO.LOW)
    log.info(f"[RELAY]   Fan=GPIO{RELAY_FAN_PIN}  "
             f"Compressor=GPIO{RELAY_COMPRESSOR_PIN}  "
             f"Pump=GPIO{RELAY_PUMP_PIN}  → all OFF")

    # Float sensor inputs — internal pull-up; active LOW when float rises
    GPIO.setup(FLOAT_SINK_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(FLOAT_TANK_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    log.info(f"[FLOAT]   Sink=GPIO{FLOAT_SINK_PIN}  Tank=GPIO{FLOAT_TANK_PIN}  (active LOW)")

    # Flow sensor
    # RPi has weak internal pull-ups (~50kΩ) — for 3.3V signals a
    # 10kΩ external pull-up to 3.3V is strongly recommended (same
    # as the ESP32 note in the original firmware).
    GPIO.setup(FLOW_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(
        FLOW_PIN,
        GPIO.FALLING,
        callback=flow_pulse_isr,
        bouncetime=2        # 2 ms debounce — adjust if you see phantom pulses
    )
    log.info(f"[FLOW]    Interrupt on GPIO{FLOW_PIN} (FALLING, bouncetime=2ms)")

def set_relays(fan: bool, compressor: bool, pump: bool) -> None:
    """Drive all three relay outputs in one atomic call.

    Args:
        fan:        True = fan relay ON (HIGH), False = OFF (LOW).
        compressor: True = compressor relay ON, False = OFF.
        pump:       True = pump relay ON, False = OFF.
    """
    GPIO.output(RELAY_FAN_PIN,        GPIO.HIGH if fan        else GPIO.LOW)
    GPIO.output(RELAY_COMPRESSOR_PIN, GPIO.HIGH if compressor else GPIO.LOW)
    GPIO.output(RELAY_PUMP_PIN,       GPIO.HIGH if pump       else GPIO.LOW)


def read_floats() -> tuple:
    """Read both float sensor inputs.

    Returns:
        (sink_triggered, tank_triggered) — each True when the float has
        risen (water present), i.e. when the GPIO reads LOW.
    """
    sink = (GPIO.input(FLOAT_SINK_PIN) == GPIO.LOW)
    tank = (GPIO.input(FLOAT_TANK_PIN) == GPIO.LOW)
    return sink, tank
