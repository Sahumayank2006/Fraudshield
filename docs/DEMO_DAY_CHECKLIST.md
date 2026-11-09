# FraudShield: Demo Day Pre-Flight Checklist (`docs/DEMO_DAY_CHECKLIST.md`)

> **Antigravity Operational Readiness & Live Demo Checklist**  
> Complete pre-flight verification procedures for running FraudShield smoothly during presentation day, faculty evaluation, or viva examination.

---

## 1. Environment & Hardware Pre-Flight (T-Minus 30 Minutes)

- [ ] **Power Adapter**: Laptop plugged in and charging (prevents CPU throttling or battery saver mode).
- [ ] **Windows Power Mode**: Set to **"Best performance"** in Windows Settings &rarr; System &rarr; Power & battery.
- [ ] **Display Resolution & Scaling**: Set resolution to $1920 \times 1080$ at $100\%$ scaling (ensures charts and SVG layouts render crisply).
- [ ] **Notifications & Distractions**: Enable **Focus Assist / Do Not Disturb**; close Slack, WhatsApp, Discord, email, and unneeded background processes.
- [ ] **Offline Resilience Test**: FraudShield is engineered to run **$100\%$ offline** without internet access. Disconnect Wi-Fi briefly and verify `http://localhost:8000` functions normally.

---

## 2. Software & Artifact Verification (T-Minus 15 Minutes)

Run these checks in PowerShell inside `c:\Users\licsa\Downloads\fraud detaction`:

```powershell
# 1. Verify virtual environment and python version (Python 3.12+)
python --version

# 2. Run full automated verification test suite (All 50 tests must pass)
python run.py test

# 3. Verify that all required pre-computed artifacts exist
python -c "
from pathlib import Path
artifacts = [
    'artifacts/model_champion.joblib',
    'artifacts/metrics.json',
    'artifacts/experiments.json',
    'artifacts/curves.json',
    'artifacts/thresholds.json',
    'artifacts/shap_summary.json',
    'artifacts/drift_monitor.json',
    'artifacts/fairness.json',
    'artifacts/datacards.json',
    'artifacts/hypotheses.json',
    'data/fraudshield.db',
]
missing = [a for a in artifacts if not Path(a).exists()]
if missing:
    print('WARNING: Missing artifacts:', missing)
else:
    print('SUCCESS: All 11 core production artifacts verified!')
"

# 4. Verify frontend production bundle exists in frontend/dist/
Test-Path "frontend/dist/index.html"
```

---

## 3. Server Startup & Launch (T-Minus 5 Minutes)

Start the unified server (FastAPI backend + static SPA frontend):

```powershell
python run.py demo
```

- Expected terminal output:
  ```
  [FraudShield] Starting unified API server and web console on http://127.0.0.1:8000
  INFO:     Started server process [PID]
  INFO:     Waiting for application startup.
  INFO:     Application startup complete.
  INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
  ```

---

## 4. Browser Setup & In-Demo Quick Checks (T-Minus 2 Minutes)

- [ ] Open **Google Chrome** or **Microsoft Edge** to `http://127.0.0.1:8000`.
- [ ] Verify the header displays:
  - Wordmark: `FraudShield`
  - Version: `v1.0-champion · Isotonic Calibrated`
  - Latency: `~3.2 ms`
  - Stream: `Live` (Green pulsing dot)
- [ ] Press **`F11`** to enter clean full-screen presentation mode.
- [ ] Quick keyboard sanity check:
  - Press **`?`** &rarr; verify Shortcuts Cheatsheet modal opens and closes with **`Esc`**.
  - Press **`P`** &rarr; verify Present Mode guided tour opens and closes with **`Esc`**.
  - Press **`A`** &rarr; verify Scripted Attack Toast banner appears.
- [ ] Press `G` then `1` to position on **§01 Executive Briefing** for the opening pitch.

---

## 5. Troubleshooting & Emergency Fallbacks

### Port 8000 Conflict
If port 8000 is occupied by another process:
```powershell
# Find and terminate conflicting process
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process -Force
# Or launch on alternative port 8080:
uvicorn api.main:app --host 127.0.0.1 --port 8080
```

### Stream Disconnection or Paused State
If the stream indicator in the header turns grey ("Paused"):
- Press **`Space`** to resume stream playback.
- Or click the **Play** button on the §02 Live Desk controls.

### Resetting Analyst Dispositions & Telemetry
If you performed test actions and want a clean slate:
- On §02 Live Desk, click the **Reset** button.
- SQLite database preserves audit logs while resetting in-memory session counters.
