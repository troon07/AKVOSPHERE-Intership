"""
Logging configuration, I2C scanning, and serial print block.
"""
import logging

logging.basicConfig(
    level=logging.DEBUG,          # change to INFO in production
    format="%(asctime)s [%(levelname)-8s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("AKVO-AWG")

def scan_i2c():
    """I2C bus scanner — mirrors ESP32 setup scan for debug."""
    import smbus2
    bus = smbus2.SMBus(1)
    found = []
    for addr in range(1, 127):
        try:
            bus.read_byte(addr)
            found.append(f"0x{addr:02X}")
        except OSError:
            pass
    bus.close()
    if found:
        log.info(f"[I2C]    Devices found: {', '.join(found)}")
    else:
        log.warning("[I2C]    !! No devices found — check wiring / pull-ups !!")

def print_serial_log():
    """Prints the current sensor state to the serial console."""
    from akvo_awg.state import state
    print("─────────────────────────────────")
    print(f"  Pipe Temp  (DS18B20) : {state.pipe_temp_c:.2f} °C")
    print(f"  Ambient Temp (SHT45) : {state.ambient_temp_c:.2f} °C")
    print(f"  Humidity     (SHT45) : {state.humidity_pct:.2f} %")
    print(f"  Flow Rate           : {state.flow_rate_lmin:.3f} L/min")
    print(f"  Total Volume        : {state.total_volume_l:.4f} L")
    print(f"  SHT45               : {'OK' if state.sht45_ok else 'FAIL'}")
    print(f"  DS18B20             : {'OK' if state.ds18b20_ok else 'FAIL'}")
    print("─────────────────────────────────\n")
