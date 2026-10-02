"""
LCD initialization, rendering with page state, and sensor value formatting.
"""
from RPLCD.i2c import CharLCD
from akvo_awg.config import LCD_I2C_ADDR, LCD_COLS, LCD_ROWS
from akvo_awg.logger import log
from akvo_awg.state import state

def fmt_sensor(val: float, decimals: int, width: int = 6) -> str:
    """Right-aligned float string, mirrors dtostrf() in Arduino."""
    return f"{val:{width}.{decimals}f}"

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
            if not state.ds18b20_ok or state.pipe_temp_c == -99.0:
                lcd.write_string("  SENSOR ERR")
            else:
                lcd.write_string(f"{fmt_sensor(state.pipe_temp_c, 1)}\xDFC ")

            lcd.cursor_pos = (1, 5)
            if not state.sht45_ok:
                lcd.write_string("  SENSOR ERR")
            else:
                lcd.write_string(f"{fmt_sensor(state.ambient_temp_c, 1)}\xDFC ")

        elif page == 1:
            # ── Page 1: Humidity + Flow Rate ──────────────────
            if page_changed:
                lcd.clear()
                lcd.cursor_pos = (0, 0); lcd.write_string("RH  :")
                lcd.cursor_pos = (1, 0); lcd.write_string("Flow:")

            lcd.cursor_pos = (0, 5)
            if not state.sht45_ok:
                lcd.write_string("  SENSOR ERR")
            else:
                lcd.write_string(f"{fmt_sensor(state.humidity_pct, 1)}%    ")

            lcd.cursor_pos = (1, 5)
            lcd.write_string(f"{fmt_sensor(state.flow_rate_lmin, 2)} L/m")

        else:
            # ── Page 2: Total Volume ───────────────────────────
            if page_changed:
                lcd.clear()
                lcd.cursor_pos = (0, 0); lcd.write_string("Total Volume:   ")

            lcd.cursor_pos = (1, 0)
            lcd.write_string(f"{state.total_volume_l:8.3f} L      ")

    except Exception as e:
        log.warning(f"[LCD]     Write error: {e}")

    _last_rendered_page = page
