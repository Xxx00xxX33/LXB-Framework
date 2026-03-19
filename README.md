# LXB-Framework

Android on-device automation framework (current focus: **APK-first workflow**).

[English](README.md) | [中文](README.zh.md)

This project has moved from the old "PC + Android linked console" style to a **phone-side execution model**:
- User enters a task directly in the Android app
- FSM runs on device
- LLM/VLM planning and action loop run from device-side service
- Task/schedule management is handled inside the app

Status: **Alpha / fast iteration**

---

## Core Capabilities

### 1) Map-Centric Route-Then-Act

LXB builds reusable app navigation maps, then executes automation in two stages:
- **Route**: deterministic navigation from entry page to target page
- **Act**: VLM-guided UI operations only after arriving at target context

This design reduces random trial-and-error actions and improves task reproducibility.

### 2) Shizuku + app_process Background Runtime

LXB launches `lxb-core` through **Shizuku + app_process** instead of relying on:
- strict `adb`-dependent workflows, or
- pure APK foreground lifecycle only

Practical result:
- better long-running stability on-device
- supports scheduler-driven auto-run tasks in real usage
- survives common app lifecycle interruptions better than APK-only execution

---

## Quick Start (Android Only)

### 1. Install Shizuku

- GitHub: https://github.com/RikkaApps/Shizuku
- Follow Shizuku official guide to start Shizuku service on your device.

Notes:
- Shizuku must be running before LXB can start its backend service.
- On Xiaomi/MIUI, set LXB battery policy to `No restrictions` to avoid background kill.

### 2. Install LXB-Ignition APK

- Download from Releases: https://github.com/wuwei-crg/LXB-Framework/releases
- Install `lxb-ignition-vX.Y.Z.apk`.

### 3. Grant permission and start backend

In LXB app:
1. Open app and grant Shizuku permission when prompted.
2. Go to Home page.
3. Tap `Start Service` (this starts the device-side lxb-core process through Shizuku).
4. Confirm service status is running.

### 4. Configure model endpoint

In Config pages, set:
- API base URL
- API key
- LLM model
- VLM model

Save config, then run a simple task (for example: "Open Bilibili and post a status update draft").

---

## Current Product Shape

- **Map-driven Route-Then-Act execution**
- **Shizuku/app_process-backed background runtime for scheduled tasks**
- FSM pipeline (init -> app resolve -> route plan -> routing -> vision act)
- Task queue + schedule execution
- Trace/status messages pushed back to app UI
- On-device persistence for config/task/schedule data

---

## Demo

### 1) MapBuilder - Navigation Map Building

<img src="resources/map_building (speed x 5).gif" alt="Map Building (5x speed)" width="700">

### 2) MapBuilder - Graph Visualization

<img src="resources/map_visualization.gif" alt="Map Visualization" width="700">

### 3) Auto Run - Order Coffee

`[GIF_PLACEHOLDER_AUTO_RUN_ORDER_COFFEE]`

### 4) Auto Run - Xuexi Qiangguo Quiz Completion

`[GIF_PLACEHOLDER_AUTO_RUN_XXQG_QUIZ]`

---

## Architecture (Placeholder)

TODO: update with new architecture diagram.

`[ARCHITECTURE_PLACEHOLDER_V2]`

Proposed diagram blocks:
- Android UI layer (Chat / Config / Tasks / Schedules)
- Command client
- lxb-core service (FSM, TaskManager, Scheduler, Trace push)
- Shizuku bridge
- Android system interaction (input, screenshot, activity, app lifecycle)
- Remote model endpoint (LLM/VLM)

---

## For Developers

Android build:

```bash
cd android/LXB-Ignition
./gradlew :app:installDebug
```

Release build (local script):

```bash
powershell -ExecutionPolicy Bypass -File .\.release_local\release\build_release.ps1 -Version X.Y.Z
```

---

## License

MIT. See [LICENSE](LICENSE).
