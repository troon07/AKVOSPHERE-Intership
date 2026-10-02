"""
Configuration constants for the AKVO AWG system.
Includes pin definitions, I2C addresses, calibration factors, and timing intervals.
"""

# ─────────────────────────────────────────────────────────────
#  PIN DEFINITIONS (BCM)
# ─────────────────────────────────────────────────────────────
FLOW_PIN  = 17    # GPIO17 → physical pin 11
# DS18B20 uses GPIO4 automatically via kernel 1-Wire driver
# (configured in /boot/config.txt — see SETUP INSTRUCTIONS)

# ─────────────────────────────────────────────────────────────
#  RELAY OUTPUT PINS (BCM) — one per component
# ─────────────────────────────────────────────────────────────
RELAY_FAN_PIN        = 27   # GPIO27 → cooling fan relay
RELAY_COMPRESSOR_PIN = 22   # GPIO22 → compressor relay
RELAY_PUMP_PIN       = 23   # GPIO23 → water pump relay

# ─────────────────────────────────────────────────────────────
#  FLOAT SENSOR INPUT PINS (BCM)
#  Both floats are active LOW — GPIO reads LOW when float is
#  triggered (water present / float risen).
# ─────────────────────────────────────────────────────────────
FLOAT_SINK_PIN = 24   # GPIO24 → internal sink float — triggers pump
FLOAT_TANK_PIN = 25   # GPIO25 → external tank float — triggers sleep

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
#  AWG CYCLE TIMING (seconds)
# ─────────────────────────────────────────────────────────────
FAN_PREHEAT_DURATION = 300    # fan runs alone before compressor (5 min)
TANK_SLEEP_DURATION  = 1800   # machine sleeps when tank is full (30 min)
PUMP_RUN_TIMEOUT     = 120    # safety: force pump off if sink won't drain (2 min)
