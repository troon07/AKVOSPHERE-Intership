"""
Initialization and reading logic for the DS18B20 temperature sensor.
"""
from w1thermsensor import W1ThermSensor, SensorNotReadyError
from akvo_awg.logger import log

def init_ds18b20():
    """Return W1ThermSensor or None on failure."""
    try:
        sensor = W1ThermSensor()
        log.info("[DS18B20] Initialized on GPIO4 (1-Wire) — OK")
        return sensor
    except Exception as e:
        log.error(f"[DS18B20] Init failed: {e}")
        log.error("[DS18B20] Check: dtoverlay=w1-gpio,gpiopin=4 in /boot/config.txt")
        log.error("[DS18B20] And:   sudo modprobe w1-gpio && sudo modprobe w1-therm")
        return None

def get_temperature(sensor):
    """Read temperature with SensorNotReadyError handling."""
    if not sensor:
        return -99.0
    try:
        return sensor.get_temperature()
    except SensorNotReadyError:
        return -99.0
    except Exception as e:
        log.warning(f"[DS18B20] Read error: {e}")
        return -99.0
