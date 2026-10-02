# 🧪 Simulation & Automated Testing

The **AKVO Automation Engine** contains an advanced telemetry simulator (`simulator.py`) designed to push deterministic IoT sensor events into the database. This allows engineers to validate backend automation rules, verify alert triggers, and dry-run wellness scoring services without needing a physical Atmospheric Water Generator connected to the network.

---

## 🗺️ Role of simulator.py in System Testing

The simulator generates sequences of time-series records that emulate specific hardware operational scenarios (both healthy and fault states). It calculates appropriate time-offsets (`esp_log_at`) and inserts them directly into the Supabase database. 

Once inserted, the scheduled backend health services query this history, allowing you to verify that the FastAPI diagnostic API (`GET /automation-health`) immediately detects the simulated anomalies.

---

## 📂 Command-Line Parameters

Run the simulator from your activated virtual environment:

```bash
python simulator.py --scenario <scenario_name> [--machine-id <custom_id>]
```

### Options:
* **`--scenario`** (Mandatory): Specifies the operational scenario to execute. Must be one of the six scenarios outlined below.
* **`--machine-id`** (Optional): Specifies the machine identifier. Defaults to **`machine_001`**.

---

## 🎭 Simulation Scenarios & Architectural Details

### 1. Normal Operation (`normal_operation`)
* **Behavior**: Simulates a clean, healthy operating cycle.
* **Sequence**:
  * Evaporator fan starts alone for 5 minutes (`fan_status=True`, `compressor_status=False`).
  * Evaporator fan continues and compressor starts up (`fan_status=True`, `compressor_status=True`). Current draws increase to ~5.6A, power peaks at ~1280W.
  * Compressor shuts down. Fan remains ON alone for 3 minutes as a cooldown phase.
  * System turns completely OFF.
* **Health Verdict**: `100% HEALTHY`

### 2. Machine Offline (`offline`)
* **Behavior**: Simulates a network adapter failure, electrical blackout, or connection dropout.
* **Sequence**: Telemetry records are written, but the last record is timestamped more than 8 minutes ago.
* **Health Verdict**: `OFFLINE` status immediately raised on `/automation-health`.

### 3. Rapid Compressor Toggling (`rapid_cycling`)
* **Behavior**: Emulates high-frequency compressor ON/OFF states within a tight 10-minute window (indicative of a faulty pressure switch or sensor threshold bounce).
* **Sequence**: Rapidly alternates compressor states (`ON` ➔ `OFF` ➔ `ON` ➔ `OFF` ➔ `ON` ➔ `OFF`) at brief 1-minute offsets.
* **Health Verdict**: `CRITICAL FAULT` - Rapid Cycling detected. Highly destructive to physical compressors.

### 4. Fan/Compressor Mismatch (`fan_mismatch`)
* **Behavior**: Simulates a serious physical cooling fan motor failure.
* **Sequence**:
  * Compressor runs cleanly.
  * Suddenly, the evaporator fan status drops to `False` (OFF) while the compressor remains `True` (ON). Current spikes to 6.2A.
  * Automatically injects a `fault_code="FAN_STOPPED"`.
* **Health Verdict**: `CRITICAL FAULT` - Fan Mismatch. If ignored on physical hardware, this leads to complete ice-over on the evaporator coils or thermal compressor locks.

### 5. Improper System Startup (`improper_startup`)
* **Behavior**: Emulates a bypass of the safety fan lead time.
* **Sequence**: The compressor is booted directly from a system-off state without first running the fan alone to establish stabilized airflow.
* **Health Verdict**: `SAFETY WARNING` - Insufficient fan lead time.

### 6. Improper System Shutdown (`improper_shutdown`)
* **Behavior**: Emulates a bypass of the safety fan cooldown time.
* **Sequence**: The compressor runs, shuts down, and the fan turns OFF immediately in the exact same minute instead of running as a cooldown phase.
* **Health Verdict**: `SAFETY WARNING` - Fan cooldown skipped.

---

## 🏃 Verification Workflow Example

Here is a step-by-step example of how to test the backend rules using the simulator:

1. **Activate your environment** and verify that your FastAPI server is running (`uvicorn app.main:app`).
2. **Execute a Fan Mismatch scenario** in a separate terminal:
   ```bash
   python simulator.py --scenario fan_mismatch --machine-id test_machine_99
   ```
3. **Inspect the terminal output**. The simulator should successfully authenticate and write the rows:
   ```text
   2026-06-01 15:35:02 INFO event=telemetry_scenario_started scenario=fan_mismatch machine_id=test_machine_99 status=running
   2026-06-01 15:35:03 INFO event=telemetry_inserted machine_id=test_machine_99 esp_log_at=2026-06-01T15:34:03 fan_status=False compressor_status=True mode=auto fault_code=FAN_STOPPED status=inserted
   2026-06-01 15:35:03 INFO event=telemetry_batch_inserted inserted_count=6 status=success
   2026-06-01 15:35:03 INFO event=telemetry_scenario_finished scenario=fan_mismatch machine_id=test_machine_99 status=success
   ```
4. **Query the health endpoint**:
   ```bash
   curl http://127.0.0.1:8000/automation-health
   ```
5. **Verify the JSON response**. The engine should automatically identify the mismatch for `test_machine_99` and flag it:
   ```json
   {
     "status": "warning",
     "window_hours": 24,
     "automations": {
       "test_machine_99": {
         "health_score": 25.0,
         "fan_mismatch_detected": true,
         "fault_code_reported": "FAN_STOPPED",
         "rapid_cycling_detected": false,
         "online_status": "online"
       }
     }
   }
   ```
   *(Note: The health score is degraded due to the safety violation, proving the backend rule engine works perfectly!)*
