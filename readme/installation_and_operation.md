# 🚀 Installation, Setup & Operation Guide

This document walks you through the step-by-step procedure of preparing a fresh **Raspberry Pi OS** installation, configuring the Linux kernel modules, installing dependencies, validating hardware connections, and deploying the **AKVO AWG Sensor Monitoring System** as a robust background system service.

---

## 🛠️ Step 1: Linux Kernel Configuration (Run Once)

The Raspberry Pi requires kernel-level drivers to communicate over the I2C bus and the 1-Wire protocol. These must be explicitly enabled.

1. Open the primary boot configuration file in the terminal:
   ```bash
   sudo nano /boot/config.txt
   ```
   *(Note: On newer Raspberry Pi OS Bookworm or later releases, this file may reside at `/boot/firmware/config.txt`)*

2. Scroll to the bottom of the file and verify or append the following lines:
   ```ini
   # Enable the hardware I2C interface (SDA/SCL on Pins 3 & 5)
   dtparam=i2c_arm=on

   # Enable 1-Wire interface and assign data pin to GPIO4 (Pin 7)
   dtoverlay=w1-gpio,gpiopin=4
   ```

3. Save the changes (`Ctrl+O`, then `Enter`) and exit the editor (`Ctrl+X`).

4. **Reboot** the Raspberry Pi to load the updated devicetree overlays:
   ```bash
   sudo reboot
   ```

---

## 📦 Step 2: System Package Installation

Once the Pi has booted up, update the local package index and install required Python environment packages and hardware scanner utilities:

```bash
sudo apt update
sudo apt install -y python3-pip python3-smbus i2c-tools python3-dev
```

---

## 🐍 Step 3: Python Environment & Dependencies

Install the specific library dependencies required for sensor interfaces and the LCD screen.

### Automatic Installation via `requirements.txt`
In the project directory, run:
```bash
pip3 install -r requirements.txt --break-system-packages
```
*(Note: `--break-system-packages` is required on newer Debian/Raspberry Pi OS versions if you are not using a Python Virtual Environment, as system-wide pip installs are blocked by default. Alternatively, configure a virtual environment).*

### Manual Library Installation
If you prefer to install packages individually, run:
```bash
pip3 install RPi.GPIO adafruit-blinka adafruit-circuitpython-sht4x RPLCD smbus2 w1thermsensor --break-system-packages
```

---

## 🔍 Step 4: Hardware Validation & Diagnostics

Before launching the software core, verify that the physical wiring is correct and the sensors are recognized by the operating system.

### A. Scanning I2C Devices (LCD & SHT45)
Run the I2C bus probe:
```bash
i2cdetect -y 1
```
Expected terminal grid output:
```text
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:                         -- -- -- -- -- -- -- --
10:          -- -- -- -- -- -- -- -- -- -- -- -- --
20:          -- -- -- -- -- -- -- 27 -- -- -- -- --
30:          -- -- -- -- -- -- -- -- -- -- -- -- --
40:             44 -- -- -- -- -- -- -- -- -- -- --
```
* **`0x27`**: PCF8574 LCD expander (if missing, check power lines or adjust address in `config.py` to `0x3F`).
* **`0x44`**: SHT45 humidity sensor.

### B. Validating the 1-Wire Bus (DS18B20)
Probe the kernel 1-Wire module:
```bash
sudo modprobe w1-gpio && sudo modprobe w1-therm
ls /sys/bus/w1/devices/
```
Expected output:
```text
28-xxxxxxxxxxxx  w1_bus_master1
```
A folder starting with **`28-`** must appear. This is your DS18B20 sensor's unique factory serial number. If this folder is absent, double-check that a **4.7kΩ pull-up resistor** is securely connected between the DS18B20 data pin and the 3.3V rail.

---

## 🏃 Step 5: Running the System

To run the orchestrated sensor monitoring application, execute the main script from the root workspace directory:

```bash
sudo python3 main.py
```
* **Why `sudo` is required**: Direct access to the Raspberry Pi's hardware registers (GPIO pins, raw memory manipulation for edge detection interrupts, I2C bus) requires superuser root privileges.

---

## ⚙️ Step 6: Deploying as a System Daemon (Run on Boot)

To ensure the AKVO AWG system automatically starts up whenever the Raspberry Pi boots and runs reliably in the background, configure it as a **systemd service**.

1. Create a new service description file:
   ```bash
   sudo nano /etc/systemd/system/akvo-awg.service
   ```

2. Paste the configuration block below (adjust the `WorkingDirectory` and script path if your codebase is located in a different path, e.g., `/home/pi/Rasp`):
   ```ini
   [Unit]
   Description=AKVO AWG Sensor Monitoring System Service
   After=multi-user.target network.target

   [Service]
   Type=simple
   ExecStart=/usr/bin/python3 /home/pi/Rasp/main.py
   WorkingDirectory=/home/pi/Rasp
   StandardOutput=journal
   StandardError=journal
   Restart=always
   RestartSec=5
   User=root

   [Install]
   WantedBy=multi-user.target
   ```

3. Reload the systemd daemon to load the new service file:
   ```bash
   sudo systemctl daemon-reload
   ```

4. Enable the service so it starts automatically at system startup:
   ```bash
   sudo systemctl enable akvo-awg.service
   ```

5. Start the background service immediately:
   ```bash
   sudo systemctl start akvo-awg.service
   ```

---

## 📊 Monitoring Logs & Troubleshooting

Once deployed, the software logs system metrics, I/O readings, state transitions, and device warnings directly to the operating system's systemd journal.

* **View live scrolling logs (real-time)**:
  ```bash
  sudo journalctl -u akvo-awg.service -f
  ```
  Expected runtime logs output:
  ```text
  14:50:02 [INFO    ] ====================================
  14:50:02 [INFO    ]    AKVO AWG — Sensor Monitor v1.1  
  14:50:02 [INFO    ]    Mithun Kumar J | Akvosphere      
  14:50:02 [INFO    ]    Platform: Raspberry Pi 3A        
  14:50:02 [INFO    ] ====================================
  14:50:02 [INFO    ] [RELAY]   Fan=GPIO27  Compressor=GPIO22  Pump=GPIO23  → all OFF
  14:50:02 [INFO    ] [FLOAT]   Sink=GPIO24  Tank=GPIO25  (active LOW)
  14:50:02 [INFO    ] [FLOW]    Interrupt on GPIO17 (FALLING, bouncetime=2ms)
  14:50:02 [INFO    ] [I2C]    Devices found: 0x27, 0x44
  14:50:03 [INFO    ] [LCD]     Initialized at 0x27
  14:50:03 [INFO    ] [SHT45]   Initialized at 0x44 — OK
  14:50:03 [INFO    ] [DS18B20] Initialized on GPIO4 (1-Wire) — OK
  14:50:04 [INFO    ] [INIT]    Setup complete
  14:50:04 [INFO    ] [AWG] STARTUP → FAN_ONLY  (fan=ON  compressor=OFF  pump=OFF)
  ```

* **Check current service status (Running/Stopped)**:
  ```bash
  sudo systemctl status akvo-awg.service
  ```

* **Stop the service**:
  ```bash
  sudo systemctl stop akvo-awg.service
  ```

* **Restart the service**:
  ```bash
  sudo systemctl restart akvo-awg.service
  ```
