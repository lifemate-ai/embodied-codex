# Health Connect Companion

Small Android companion app that reads the latest heart-rate sample from Health Connect
and posts it to the local embodied-codex ingest bridge.

## What it does

- requests `READ_HEART_RATE` from Health Connect
- reads the latest heart-rate sample visible to Health Connect
- sends JSON to a configured LAN endpoint
- writes the same payload shape that continuity already understands

## Current scope

- manual send
- periodic send via WorkManager
- heart rate only for the first pass

## Expected endpoint

Point the app at:

`http://<your-lan-host>:8765/ingest`

The matching local receiver lives at:

[`scripts/companion-biometrics-ingest.py`](../scripts/companion-biometrics-ingest.py)

## Deploy

1. Start the local receiver on the embodied-codex host:

   ```bash
   cd /home/mizushima/embodied-codex
   cp .env.example .env
   python3 ./scripts/companion-biometrics-ingest.py
   ```

2. Verify the receiver:

   ```bash
   curl http://127.0.0.1:8765/healthz
   ```

3. Open this directory in Android Studio.

4. Use **JDK 21** for Gradle / Android Studio.

5. Build and install the app on the phone.

6. In the app, set:
   - `Endpoint URL` = `http://<LAN-IP-of-the-embodied-codex-host>:8765/ingest`
   - `Bearer token` = same value as `CODEX_COMPANION_BIOMETRICS_INGEST_TOKEN` if you
     enabled auth

7. Tap `Grant permission` for foreground reads.

8. If the device/provider supports it, tap `Grant background` too. This is required for
   WorkManager-based periodic reads.

9. Tap `Preview latest HR` to confirm the latest heart-rate sample is visible.

10. Tap `Send to embodied-codex` once.

11. If that works, tap `Enable periodic send`.

## Periodic send behavior

- uses `WorkManager.enqueueUniquePeriodicWork()`
- requires network connectivity
- minimum interval is **15 minutes**
- background reads require
  `android.permission.health.READ_HEALTH_DATA_IN_BACKGROUND`
- the app only schedules periodic work after you explicitly enable it in the UI

Current interval presets in the UI:

- `15m`
- `30m`
- `60m`

## Build notes

This project is intended to be opened in Android Studio. The repository includes a Gradle
wrapper, but this workspace does not currently have the Android SDK installed and the
default shell JDK here is `25`, so the app was scaffolded and reviewed statically rather
than built locally here. The intended setup is Android Studio + JDK 21.
