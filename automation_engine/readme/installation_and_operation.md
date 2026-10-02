# 🚀 Installation, Setup & Operation Guide

This guide walks you through setting up, configuring, and operating the **AKVO Automation Engine Backend** locally or in a production environment.

---

## 🛠️ Step 1: Environment & Virtual Environment Setup

Ensure you have **Python 3.10+** installed on your system.

1. **Clone or navigate** to the project subdirectory:
   ```bash
   cd "automation_engine - Copy/automation_engine - Copy"
   ```

2. **Initialize a virtual environment** to isolate dependencies:
   * **Windows (PowerShell/CMD)**:
     ```powershell
     python -m venv .venv
     .venv\Scripts\activate
     ```
   * **macOS / Linux**:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

---

## 📦 Step 2: Install Package Dependencies

With the virtual environment active, install the required packages:

```bash
pip install -r requirements.txt
```

---

## ⚙️ Step 3: Dotenv (.env) Configuration

Centralized settings are read from a local `.env` file. We provide a `.env.example` to get started.

1. **Duplicate the example settings file**:
   * **Windows (PowerShell)**:
     ```powershell
     Copy-Item .env.example .env
     ```
   * **Linux / macOS**:
     ```bash
     cp .env.example .env
     ```

2. **Open `.env` in a text editor** and fill in your Supabase connection parameters:
   ```ini
   APP_NAME="AKVO Automation Engine"
   LOG_LEVEL=info

   # Supabase Credentials (from your Supabase Project Settings > API)
   SUPABASE_URL=https://your-project-id.supabase.co
   SUPABASE_KEY=your-anon-or-service-role-api-key
   ```

---

## 🏃 Step 4: Run the Application Server

Start the FastAPI application using **Uvicorn** (the high-performance ASGI server):

```bash
uvicorn app.main:app --reload
```
* **`--reload`**: Enables auto-reload on code modifications (highly recommended for local development).

Expected output:
```text
INFO:     Started server process [18432]
INFO:     Waiting for application startup.
INFO:     Scheduler started successfully.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

---

## 🔍 Step 5: REST API Endpoint Diagnostics

The FastAPI server exposes several HTTP GET endpoints to query system health, scheduled automation diagnostics, and fleet wellness summaries. You can test these in your browser or via `curl`:

### A. Core System Health Check
Validates connectivity to the Supabase PostgreSQL database and confirms that the background task scheduler is actively running.
* **Request**:
  ```bash
  curl http://127.0.0.1:8000/health
  ```
* **Response Output**:
  ```json
  {
    "status": "ok",
    "service": "AKVO Automation Engine",
    "scheduler_running": true,
    "supabase_connected": true,
    "registered_automations": 4
  }
  ```

### B. Fleet Operation & Automation Health
Returns aggregated wellness indicators for the connected AWG fleet by analyzing the telemetry history over the last 24 hours.
* **Request**:
  ```bash
  curl http://127.0.0.1:8000/automation-health
  ```

### C. Scheduler Automation Metrics
Queries execution summaries, run durations, success ratios, and failure logs for all background tasks.
* **Request**:
  ```bash
  curl http://127.0.0.1:8000/automation-metrics
  ```

### D. Validation Diagnostics Metrics
Queries verification logs, edge check metrics, and device communication health stats.
* **Request**:
  ```bash
  curl http://127.0.0.1:8000/validation-metrics
  ```
