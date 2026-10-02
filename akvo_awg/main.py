"""
Orchestration loop — imports all modules, runs tasks on monotonic timers.
"""
import time
import RPi.GPIO as GPIO

from akvo_awg.config import (
    FLOW_CALC_INTERVAL,
    SENSOR_READ_INTERVAL,
    LCD_PAGE_INTERVAL,
    SERIAL_LOG_INTERVAL,
    LOOP_SLEEP
)
from akvo_awg.logger import log, scan_i2c, print_serial_log
from akvo_awg.state import state
from akvo_awg.gpio_setup import init_gpio
from akvo_awg.relay_logic import update_awg_state
from akvo_awg.lcd import init_lcd, render_lcd
from akvo_awg.flow import calculate_flow
from akvo_awg.sensors.sht45 import init_sht45, read_sht45
from akvo_awg.sensors.ds18b20 import init_ds18b20, get_temperature

def main():
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
    sht45    = init_sht45()
    state.sht45_ok   = (sht45   is not None)
    ds18b20  = init_ds18b20()
    state.ds18b20_ok = (ds18b20 is not None)

    if not state.sht45_ok and lcd:
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
                calculate_flow()
                t_flow = now

            # ── TASK 2: Read sensors (every 1 s) ──────────────
            if now - t_sensor >= SENSOR_READ_INTERVAL:
                # DS18B20
                if state.ds18b20_ok:
                    state.pipe_temp_c = get_temperature(ds18b20)

                # SHT45 — retry init if it failed at boot and read logic
                sht45 = read_sht45(sht45)

                t_sensor = now

            # ── TASK 3: Serial log (every 2 s) ────────────────
            if now - t_serial >= SERIAL_LOG_INTERVAL:
                print_serial_log()
                t_serial = now

            # ── TASK 4: LCD paged display (rotates every 3 s) ─
            if now - t_lcd >= LCD_PAGE_INTERVAL:
                lcd_page = (lcd_page + 1) % 3
                t_lcd = now

            render_lcd(lcd, lcd_page)

            # ── TASK 5: Relay logic ────────────────────────────
            update_awg_state(now)

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
