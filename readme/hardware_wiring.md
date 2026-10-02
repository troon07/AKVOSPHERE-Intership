# 🔌 Hardware Wiring & Pin Configurations

This document provides a detailed breakdown of the hardware components, electrical characteristics, BCM-to-Physical pin mappings, and wiring requirements for the **AKVO AWG (Atmospheric Water Generator) Sensor Monitoring System** running on a **Raspberry Pi 3A**.

---

## 📌 GPIO Pin Mapping Table

The software is configured to use the **BCM (Broadcom) GPIO numbering scheme**. Below is the complete pin-out mapping:

| Component Name | Description | BCM Pin | Physical Pin | I/O Direction | Electrical Details |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **DS18B20** | Pipe Temp Sensor (1-Wire) | **GPIO 4** | Pin 7 | Input | Requires kernel 1-Wire driver & 4.7kΩ pull-up to 3.3V |
| **SHT45 SDA** | Ambient Temp & RH (I2C) | **GPIO 2** | Pin 3 | Bidirectional | I2C1 Data. Hardware pulled-up on Pi |
| **SHT45 SCL** | Ambient Temp & RH (I2C) | **GPIO 3** | Pin 5 | Output | I2C1 Clock. Hardware pulled-up on Pi |
| **LCD SDA** | 16x2 Display (I2C via PCF8574) | **GPIO 2** | Pin 3 | Bidirectional | Shared I2C1 Data line |
| **LCD SCL** | 16x2 Display (I2C via PCF8574) | **GPIO 3** | Pin 5 | Output | Shared I2C1 Clock line |
| **MR-L10-S** | Hall Effect Flow Sensor | **GPIO 17** | Pin 11 | Input | Falling-edge Interrupt. Needs external 10kΩ pull-up |
| **FLOAT_SINK** | Internal Sink Level Float | **GPIO 24** | Pin 18 | Input (PUD_UP) | Active LOW (Closed/LOW when water present) |
| **FLOAT_TANK** | External Storage Tank Float | **GPIO 25** | Pin 22 | Input (PUD_UP) | Active LOW (Closed/LOW when tank full) |
| **RELAY_FAN** | Condenser Cooling Fan Relay | **GPIO 27** | Pin 13 | Output | Active HIGH (GPIO HIGH = Fan ON) |
| **RELAY_COMP** | Compressor Power Relay | **GPIO 22** | Pin 15 | Output | Active HIGH (GPIO HIGH = Compressor ON) |
| **RELAY_PUMP** | Water Extraction Pump Relay | **GPIO 23** | Pin 16 | Output | Active HIGH (GPIO HIGH = Pump ON) |

---

## ⚡ Critical Electrical & Wiring Considerations

### 1. 1-Wire Bus (DS18B20 Temperature Sensor) 🌡️
* **Wiring**: Connect DS18B20 `VCC` to 3.3V, `GND` to Ground, and `DATA` to BCM **GPIO 4**.
* **Pull-Up Resistor**: A **4.7kΩ resistor** must be connected between `DATA` and `VCC` (3.3V) as a pull-up. Without this, the Pi's kernel driver will fail to detect the sensor, resulting in the `/sys/bus/w1/devices/` folder remaining empty.
* **Driver configuration**: Must enable `dtoverlay=w1-gpio,gpiopin=4` in `/boot/config.txt` (or `/boot/firmware/config.txt` on newer OS releases).

### 2. I2C Bus Sharing (SHT45 & 16x2 LCD) 📺
* **Bus Designation**: Both the SHT45 high-precision humidity/temperature sensor and the 16x2 paged LCD (interfaced via PCF8574 backpack) share the hardware I2C bus `I2C1` (`SDA = GPIO2`, `SCL = GPIO3`).
* **Address Conflicts**: There are no address conflicts:
  * **SHT45**: Fixed at `0x44`
  * **LCD (PCF8574)**: Typically `0x27` (or `0x3F` depending on backpack sub-model)
* **Pull-Ups**: The Raspberry Pi has built-in physical 1.8kΩ pull-up resistors on GPIO 2 and GPIO 3 to 3.3V, so no external pull-up resistors are required for the I2C lines.

### 3. MR-L10-S Hall-Effect Flow Sensor 💧
* **Power Supply**: The MR-L10-S flow sensor must be powered appropriately. If using a 5V model, ensure you use a voltage divider or level shifter on the signal line before routing it to the Pi's GPIO to prevent damage. If operating at 3.3V, direct connection is safe.
* **Signal Pull-Up**: RPi internal pull-up resistors are relatively weak (~50kΩ). For clean, reliable pulse edges and to prevent phantom counts caused by electrical noise, an **external 10kΩ resistor** between the flow signal line and the 3.3V rail is highly recommended.
* **Software Debouncing**: The software configures a `bouncetime` of **2 milliseconds** in `RPi.GPIO`'s interrupt configuration to filter out micro-switch bounce or transient spikes.

### 4. Float level Sensors 🌊
* **Safety Mechanism**: Both the Internal Sink Float and External Tank Float are wired as **active LOW** inputs.
* **Wiring**: One terminal of each float switch connects to GND, and the other connects directly to the respective BCM pin (**GPIO 24** for Sink, **GPIO 25** for Tank).
* **Software Config**: The pins are initialized with internal software pull-up resistors enabled (`pull_up_down=GPIO.PUD_UP`). 
  * When the float is dry/down, the switch is open and the GPIO reads `HIGH` (logical `False`).
  * When the float rises (water present/full), the switch closes to GND and the GPIO reads `LOW` (logical `True`).

### 5. Active Relay Driver Blocks 🔌
* **Isolation**: It is strongly advised to use **optocoupled relay boards** to isolate the Raspberry Pi's GPIO pins from the high inductive currents drawn by the fan, compressor, and pump.
* **Direct Drive Hazard**: The Pi's GPIO pins can source/sink a maximum of **16mA** each (with a total cumulative limit of ~50mA across all pins). Connecting raw relay coils directly to GPIO pins will damage the Broadcom SoC. Ensure the relay board uses active-high optoisolator inputs and has external power (e.g., 5V) for the coils.
