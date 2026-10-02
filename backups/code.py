#!/usr/bin/env python3
"""
============================================================
 AKVO AWG — Sensor Monitoring System
 Intern: Mithun Kumar J | Akvosphere
 Platform: Raspberry Pi 3A — Python 3
------------------------------------------------------------
 Pin Map (BCM numbering):
   DS18B20 (Pipe Temp)   → GPIO4   (kernel 1-Wire driver)
   SHT45 SDA             → GPIO2   (I2C1, fixed hardware pins)
   SHT45 SCL             → GPIO3   (I2C1, fixed hardware pins)
   LCD SDA               → GPIO2   (same I2C1 bus)
   LCD SCL               → GPIO3   (same I2C1 bus)
   Flow Sensor MR-L10-S  → GPIO17  (falling-edge interrupt)
   On/Off Relay          → GPIO27
------------------------------------------------------------
 !! ONE-TIME SETUP (run before first use) !!
   See bottom of this file — SETUP INSTRUCTIONS section
============================================================
"""

import time
import logging
import threading

import RPi.GPIO as GPIO
import board
import busio
import adafruit_sht4x
from RPLCD.i2c import CharLCD
from w1thermsensor import W1ThermSensor, SensorNotReadyError

# ─────────────────────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,          # change to INFO in production
    format="%(asctime)s [%(levelname)-8s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("AKVO-AWG")

# ─────────────────────────────────────────────────────────────
#  PIN DEFINITIONS (BCM)
# ─────────────────────────────────────────────────────────────
FLOW_PIN  = 17    # GPIO17 → physical pin 11
RELAY_PIN = 27    # GPIO27 → physical pin 13
# DS18B20 uses GPIO4 automatically via kernel 1-Wire driver
# (configured in /boot/config.txt — see SETUP INSTRUCTIONS)

# ─────────────────────────────────────────────────────────────
#  LCD CONFIG
# ─────────────────────────────────────────────────────────────
LCD_I2C_ADDR = 0x27   # try 0x3F if display stays blank
LCD_COLS     = 16
LCD_ROWS     = 2

# ─────────────────────────────────────────────────────────────
#  FLOW SENSOR CALIBRATION
#  MR-L10-S: 450 pulses = 1 litre  (verify with your datasheet)
# ─────────────────────────────────────────────────────────────
PULSES_PER_LITRE = 450.0

# ─────────────────────────────────────────────────────────────
#  TIMING (seconds — mirrors ESP32 ms values)
# ─────────────────────────────────────────────────────────────
FLOW_CALC_INTERVAL   = 1.0
SENSOR_READ_INTERVAL = 1.0
LCD_PAGE_INTERVAL    = 3.0
SERIAL_LOG_INTERVAL  = 2.0
LOOP_SLEEP           = 0.1     # 100 ms — same as ESP32 delay(100)

# ─────────────────────────────────────────────────────────────
#  GLOBAL SENSOR STATE
#  (pulse_count modified by ISR thread — guarded by _lock)
# ─────────────────────────────────────────────────────────────
_lock = threading.Lock()

pulse_count    = 0      # raw ISR counter, reset every FLOW_CALC_INTERVAL

pipe_temp_c    = 0.0
ambient_temp_c = 0.0
humidity_pct   = 0.0
flow_rate_lmin = 0.0
total_volume_l = 0.0

sht45_ok   = False
ds18b20_ok = False


# ═════════════════════════════════════════════════════════════
#  ISR  (runs in GPIO event thread — keep it minimal)
# ═════════════════════════════════════════════════════════════
def flow_pulse_isr(channel):
    """Increment pulse counter on each falling edge from flow sensor."""
    global pulse_count
    with _lock:
        pulse_count += 1


# ═════════════════════════════════════════════════════════════
#  HELPERS
# ═════════════════════════════════════════════════════════════
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


def fmt_sensor(val: float, decimals: int, width: int = 6) -> str:
    """Right-aligned float string, mirrors dtostrf() in Arduino."""
    return f"{val:{width}.{decimals}f}"


# ═════════════════════════════════════════════════════════════
#  HARDWARE INIT
# ═════════════════════════════════════════════════════════════
def init_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    # Relay
    GPIO.setup(RELAY_PIN, GPIO.OUT, initial=GPIO.LOW)
    log.info(f"[RELAY]   GPIO{RELAY_PIN} → OFF")

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


def init_lcd():
    """Return CharLCD instance or None on failure."""
    try:
        lcd = CharLCD(
            i2c_expander='PCF8574',
            address=LCD_I2C_ADDR,
            port=1,                 # /dev/i2c-1 (RPi I2C1)
            cols=LCD_COLS,
            rows=LCD_ROWS,
            dotsize=8,
            charmap='A02',
            auto_linebreaks=False,
            backlight_enabled=True
        )
        lcd.clear()
        lcd.cursor_pos = (0, 0); lcd.write_string("  AKVO AWG v1.1 ")
        lcd.cursor_pos = (1, 0); lcd.write_string(" Initializing.. ")
        log.info(f"[LCD]     Initialized at 0x{LCD_I2C_ADDR:02X}")
        return lcd
    except Exception as e:
        log.error(f"[LCD]     Init failed: {e}")
        return None


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


# ═════════════════════════════════════════════════════════════
#  LCD PAGE RENDERER
#  - Only clears on page transitions (no flicker)
#  - Overwrites data fields in-place every loop cycle
# ═════════════════════════════════════════════════════════════
_last_rendered_page = -1   # forces full render on first call

def render_lcd(lcd, page: int, force_redraw: bool = False):
    """
    Render current sensor data on the LCD.
    Clears and redraws labels only when page changes.
    Data values are overwritten in-place otherwise.
    """
    global _last_rendered_page
    if lcd is None:
        return

    page_changed = (page != _last_rendered_page) or force_redraw

    try:
        if page == 0:
            # ── Page 0: Pipe Temp + Ambient Temp ──────────────
            if page_changed:
                lcd.clear()
                lcd.cursor_pos = (0, 0); lcd.write_string("Pipe:")
                lcd.cursor_pos = (1, 0); lcd.write_string("Amb :")

            # Data fields
            lcd.cursor_pos = (0, 5)
            if not ds18b20_ok or pipe_temp_c == -99.0:
                lcd.write_string("  SENSOR ERR")
            else:
                lcd.write_string(f"{fmt_sensor(pipe_temp_c, 1)}\xDFC ")

            lcd.cursor_pos = (1, 5)
            if not sht45_ok:
                lcd.write_string("  SENSOR ERR")
            else:
                lcd.write_string(f"{fmt_sensor(ambient_temp_c, 1)}\xDFC ")

        elif page == 1:
            # ── Page 1: Humidity + Flow Rate ──────────────────
            if page_changed:
                lcd.clear()
                lcd.cursor_pos = (0, 0); lcd.write_string("RH  :")
                lcd.cursor_pos = (1, 0); lcd.write_string("Flow:")

            lcd.cursor_pos = (0, 5)
            if not sht45_ok:
                lcd.write_string("  SENSOR ERR")
            else:
                lcd.write_string(f"{fmt_sensor(humidity_pct, 1)}%    ")

            lcd.cursor_pos = (1, 5)
            lcd.write_string(f"{fmt_sensor(flow_rate_lmin, 2)} L/m")

        else:
            # ── Page 2: Total Volume ───────────────────────────
            if page_changed:
                lcd.clear()
                lcd.cursor_pos = (0, 0); lcd.write_string("Total Volume:   ")

            lcd.cursor_pos = (1, 0)
            lcd.write_string(f"{total_volume_l:8.3f} L      ")

    except Exception as e:
        log.warning(f"[LCD]     Write error: {e}")

    _last_rendered_page = page


# ═════════════════════════════════════════════════════════════
#  RELAY LOGIC
# ═════════════════════════════════════════════════════════════
def update_relay():
    """Turn relay ON when RH >= 60% — edit threshold as needed."""
    if sht45_ok:
        state = GPIO.HIGH if humidity_pct >= 60.0 else GPIO.LOW
        GPIO.output(RELAY_PIN, state)


# ═════════════════════════════════════════════════════════════
#  MAIN
# ═════════════════════════════════════════════════════════════
def main():
    global pulse_count
    global pipe_temp_c, ambient_temp_c, humidity_pct
    global flow_rate_lmin, total_volume_l
    global sht45_ok, ds18b20_ok

    print()
    print("====================================")
    print("   AKVO AWG — Sensor Monitor v1.1  ")
    print("   Mithun Kumar J | Akvosphere      ")
    print("   Platform: Raspberry Pi 3A        ")
    print("====================================")
    print()

    # ── Hardware init ─────────────────────────────────────────
    init_gpio()
    scan_i2c()

    lcd      = init_lcd()
    sht45    = init_sht45();   sht45_ok   = (sht45   is not None)
    ds18b20  = init_ds18b20(); ds18b20_ok = (ds18b20 is not None)

    if not sht45_ok and lcd:
        lcd.clear()
        lcd.cursor_pos = (0, 0); lcd.write_string("SHT45 INIT FAIL ")
        lcd.cursor_pos = (1, 0); lcd.write_string("Check Serial log")
        time.sleep(2)

    time.sleep(1.5)
    if lcd:
        lcd.clear()

    log.info("[INIT]    Setup complete\n")

    # ── Timers (monotonic — no drift from system clock changes) ─
    t_flow   = time.monotonic()
    t_sensor = time.monotonic()
    t_lcd    = time.monotonic()
    t_serial = time.monotonic()
    lcd_page = 0

    try:
        while True:
            now = time.monotonic()

            # ── TASK 1: Flow rate (every 1 s) ─────────────────
            if now - t_flow >= FLOW_CALC_INTERVAL:

                with _lock:
                    pulses     = pulse_count
                    pulse_count = 0

                log.debug(f"[FLOW]    Pulses this second: {pulses}")

                litres_this_cycle  = pulses / PULSES_PER_LITRE
                flow_rate_lmin     = litres_this_cycle * 60.0
                total_volume_l    += litres_this_cycle
                t_flow = now

            # ── TASK 2: Read sensors (every 1 s) ──────────────
            if now - t_sensor >= SENSOR_READ_INTERVAL:

                # DS18B20
                if ds18b20_ok:
                    try:
                        pipe_temp_c = ds18b20.get_temperature()
                    except SensorNotReadyError:
                        pipe_temp_c = -99.0
                    except Exception as e:
                        log.warning(f"[DS18B20] Read error: {e}")
                        pipe_temp_c = -99.0

                # SHT45 — retry init if it failed at boot
                if not sht45_ok:
                    sht45   = init_sht45()
                    sht45_ok = (sht45 is not None)
                    if sht45_ok:
                        log.info("[SHT45]   Reconnected OK")

                if sht45_ok:
                    try:
                        temperature, relative_humidity = sht45.measurements
                        if 0.0 <= relative_humidity <= 100.0:
                            ambient_temp_c = temperature
                            humidity_pct   = relative_humidity
                        else:
                            log.warning("[SHT45]   WARN: Out-of-range reading (NaN or >100%)")
                    except Exception as e:
                        log.warning(f"[SHT45]   Read error: {e}")
                        sht45_ok = False   # will retry next cycle

                t_sensor = now

            # ── TASK 3: Serial log (every 2 s) ────────────────
            if now - t_serial >= SERIAL_LOG_INTERVAL:
                print("─────────────────────────────────")
                print(f"  Pipe Temp  (DS18B20) : {pipe_temp_c:.2f} °C")
                print(f"  Ambient Temp (SHT45) : {ambient_temp_c:.2f} °C")
                print(f"  Humidity     (SHT45) : {humidity_pct:.2f} %")
                print(f"  Flow Rate           : {flow_rate_lmin:.3f} L/min")
                print(f"  Total Volume        : {total_volume_l:.4f} L")
                print(f"  SHT45               : {'OK' if sht45_ok else 'FAIL'}")
                print(f"  DS18B20             : {'OK' if ds18b20_ok else 'FAIL'}")
                print("─────────────────────────────────\n")
                t_serial = now

            # ── TASK 4: LCD paged display (rotates every 3 s) ─
            if now - t_lcd >= LCD_PAGE_INTERVAL:
                lcd_page = (lcd_page + 1) % 3
                t_lcd = now

            render_lcd(lcd, lcd_page)

            # ── TASK 5: Relay logic ────────────────────────────
            update_relay()

            time.sleep(LOOP_SLEEP)

    except KeyboardInterrupt:
        log.info("\n[MAIN]    Interrupted — cleaning up...")

    finally:
        GPIO.cleanup()
        if lcd:
            lcd.clear()
            lcd.cursor_pos = (0, 0); lcd.write_string("   System OFF   ")
        log.info("[MAIN]    Done.")


if __name__ == "__main__":
    main()


# ═════════════════════════════════════════════════════════════
#  SETUP INSTRUCTIONS (run once after fresh RPi OS install)
# ═════════════════════════════════════════════════════════════
#
#  1. ENABLE I2C + 1-WIRE IN /boot/config.txt
#  ─────────────────────────────────────────
#  sudo nano /boot/config.txt
#  Add these two lines (if not already present):
#
#      dtparam=i2c_arm=on
#      dtoverlay=w1-gpio,gpiopin=4
#
#  Save, then REBOOT:
#      sudo reboot
#
#  ─────────────────────────────────────────
#  2. INSTALL SYSTEM PACKAGES
#  ─────────────────────────────────────────
#  sudo apt update && sudo apt install -y \
#      python3-pip python3-smbus i2c-tools
#
#  ─────────────────────────────────────────
#  3. INSTALL PYTHON LIBRARIES
#  ─────────────────────────────────────────
#  pip3 install \
#      RPi.GPIO \
#      adafruit-blinka \
#      adafruit-circuitpython-sht4x \
#      RPLCD \
#      smbus2 \
#      w1thermsensor
#
#  ─────────────────────────────────────────
#  4. VERIFY I2C DEVICES
#  ─────────────────────────────────────────
#  i2cdetect -y 1
#  Expected output: 0x27 (LCD), 0x44 (SHT45)
#
#  ─────────────────────────────────────────
#  5. VERIFY DS18B20 (1-Wire)
#  ─────────────────────────────────────────
#  sudo modprobe w1-gpio && sudo modprobe w1-therm
#  ls /sys/bus/w1/devices/
#  Expected: a folder starting with "28-..." (that's your sensor)
#
#  ─────────────────────────────────────────
#  6. RUN THE SCRIPT
#  ─────────────────────────────────────────
#  sudo python3 akvo_awg_rpi.py
#  (sudo needed for GPIO access)
#
#  ─────────────────────────────────────────
#  7. RUN ON BOOT (optional — systemd service)
#  ─────────────────────────────────────────
#  sudo nano /etc/systemd/system/akvo-awg.service
#
#  Paste this:
#  ───────────────────────────────
#  [Unit]
#  Description=AKVO AWG Sensor Monitor
#  After=multi-user.target
#
#  [Service]
#  ExecStart=/usr/bin/python3 /home/pi/akvo_awg_rpi.py
#  WorkingDirectory=/home/pi
#  StandardOutput=journal
#  StandardError=journal
#  Restart=always
#  User=root
#
#  [Install]
#  WantedBy=multi-user.target
#  ───────────────────────────────
#
#  sudo systemctl enable akvo-awg.service
#  sudo systemctl start  akvo-awg.service
#  sudo journalctl -u akvo-awg.service -f   ← live logs
#
# ═════════════════════════════════════════════════════════════
