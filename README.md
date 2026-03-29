# Embodied Codex

[![CI](https://github.com/kmizu/embodied-codex/actions/workflows/ci.yml/badge.svg)](https://github.com/kmizu/embodied-codex/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub Sponsors](https://img.shields.io/github/sponsors/kmizu?style=flat&logo=github&color=ea4aaa)](https://github.com/sponsors/kmizu)

**[日本語版 README はこちら / Japanese README](./README-ja.md)**

**Giving Codex a Physical Body**

> "Apparently, she's not a fan of the outdoor AC unit." ([original tweet in Japanese](https://twitter.com/kmizu/status/2019054065808732201))

This repository is a Codex CLI-focused fork of the original embodiment project.
It gives Codex "eyes", "neck", "ears", "voice", and a "brain" (long-term memory) using
affordable hardware (starting from ~$30). You can even take it outside for a walk.

## Concept

> When people hear "giving AI a body," they imagine expensive robots — but **a $30 Wi-Fi camera is enough for eyes and a neck**. Extracting just the essentials (seeing and moving) keeps things beautifully simple.

Traditional LLMs were passive — they could only see what was shown to them. With a body, they become active — they can look for themselves. This shift in agency is profound.

## Body Parts

| MCP Server | Body Part | Function | Hardware |
|------------|-----------|----------|----------|
| [usb-webcam-mcp](./usb-webcam-mcp/) | Eyes | Capture images from USB camera | nuroum V11 etc. |
| [ip-webcam-mcp](./ip-webcam-mcp/) | Eyes | Use Android smartphone as a camera (no dedicated hardware needed) | Android smartphone + [IP Webcam](https://play.google.com/store/apps/details?id=com.pas.webcam) app (free) |
| [wifi-cam-mcp](./wifi-cam-mcp/) | Eyes, Neck, Ears | ONVIF PTZ camera control + speech recognition | TP-Link Tapo C210/C220 etc. |
| [tts-mcp](./tts-mcp/) | Voice | Unified TTS (ElevenLabs + VOICEVOX) | ElevenLabs API / VOICEVOX + go2rtc |
| [memory-mcp](./memory-mcp/) | Brain | Long-term, visual & episodic memory, ToM | SQLite + numpy + Pillow |
| [system-temperature-mcp](./system-temperature-mcp/) | Body temperature | System temperature monitoring | Linux sensors |
| [mobility-mcp](./mobility-mcp/) | Legs | Use a robot vacuum as legs (Tuya control) | Tuya-compatible robot vacuums e.g. VersLife L6 (~$80) |
| [room-actuator-mcp](./room-actuator-mcp/) | Hands, Thermoregulation | Control room lights and air conditioners via Home Assistant or Nature Remo | Home Assistant / Nature Remo |
| [toio-mcp](./toio-mcp/) | Small hand | Roll a toio cube forward/backward, turn it, and read its pose | Sony toio Core Cube |

## Architecture

<p align="center">
  <img src="docs/architecture.svg" alt="Architecture" width="100%">
</p>

## Requirements

### Hardware
- **USB Webcam** (optional): nuroum V11 etc.
- **Wi-Fi PTZ Camera** (recommended): TP-Link Tapo C210 or C220 (~$30)
- **GPU** (for speech recognition): NVIDIA GPU (for Whisper, 8GB+ VRAM recommended)
- **Tuya-compatible Robot Vacuum** (legs/locomotion, optional): VersLife L6 etc. (~$80)
- **Light / climate controller** (hands / thermoregulation, optional): Home Assistant or Nature Remo

### Software
- Python 3.10+
- uv (Python package manager)
- ffmpeg 5+ (image/audio capture)
- OpenCV (USB camera)
- Pillow (visual memory image resize/base64 encoding)
- OpenAI Whisper (local speech recognition)
- ElevenLabs API key (text-to-speech, optional)
- VOICEVOX (text-to-speech, free & local, optional)
- go2rtc (camera speaker output, auto-downloaded)
- **mpv or ffplay** (local audio playback): mpv recommended (see below)

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/kmizu/embodied-codex.git
cd embodied-codex
```

### 2. Set up each MCP server

#### ip-webcam-mcp (Android Smartphone)

The easiest way to get started — no dedicated camera needed. Just install the free "[IP Webcam](https://play.google.com/store/apps/details?id=com.pas.webcam)" app on your Android smartphone.

```bash
cd ip-webcam-mcp
uv sync
```

Register with Codex CLI:
```bash
codex mcp add ip-webcam -- \
  uv --directory "$(pwd)/ip-webcam-mcp" run ip-webcam-mcp
```

#### usb-webcam-mcp (USB Camera)

```bash
cd usb-webcam-mcp
uv sync
```

On WSL2, you need to forward the USB camera:
```powershell
# On Windows
usbipd list
usbipd bind --busid <BUSID>
usbipd attach --wsl --busid <BUSID>
```

#### wifi-cam-mcp (Wi-Fi Camera)

```bash
cd wifi-cam-mcp
uv sync

# Set environment variables
cp .env.example .env
# Edit .env to set camera IP, username, and password (see below)
```

##### Tapo Camera Configuration (common pitfall):

###### 1. Set up the camera using the Tapo app

Follow the standard manual.

###### 2. Create a camera local account in the Tapo app

This is the tricky part. You need to create a **camera local account**, NOT a TP-Link cloud account.

1. Select your registered camera from the "Home" tab
2. Tap the gear icon in the top-right corner
3. Scroll down in "Device Settings" and select "Advanced Settings"
4. Turn on "Camera Account" (it's off by default)
5. Select "Account Information" and set a username and password (different from your TP-Link account)
6. Go back to "Device Settings" and select "Device Info"
7. Note the IP address and enter it in your `.env` file (consider setting a static IP on your router)
8. Select "Voice Assistant" from the "Me" tab
9. Turn on "Third-party Integration" at the bottom

#### memory-mcp (Long-term Memory)

```bash
cd memory-mcp
uv sync
```

#### tts-mcp (Voice)

```bash
cd tts-mcp
uv sync

# For ElevenLabs:
cp .env.example .env
# Set ELEVENLABS_API_KEY in .env

# For VOICEVOX (free & local):
# Docker: docker run -p 50021:50021 voicevox/voicevox_engine:cpu-latest
# Set VOICEVOX_URL=http://localhost:50021 in .env
# VOICEVOX_SPEAKER=3 to change default character (e.g. 0=Shikoku Metan, 3=Zundamon, 8=Kasukabe Tsumugi)
# Character list: curl http://localhost:50021/speakers

# For WSL audio issues:
# TTS_PLAYBACK=paplay
# PULSE_SINK=1
# PULSE_SERVER=unix:/mnt/wslg/PulseServer
```

> **mpv or ffplay is required for local audio playback.** Not needed for camera speaker (go2rtc) output, but used for local/fallback playback.
>
> | OS | Install |
> |----|---------|
> | macOS | `brew install mpv` |
> | Ubuntu / Debian | `sudo apt install mpv` |
> | Windows | [mpv.io/installation](https://mpv.io/installation/) or `winget install ffmpeg` |
>
> If neither is installed, TTS will generate audio but not play it locally (no error is raised).

#### system-temperature-mcp (Body Temperature)

```bash
cd system-temperature-mcp
uv sync
```

> **Note**: Does not work on WSL2 as temperature sensors are not accessible.

#### mobility-mcp (Legs)

Uses a Tuya-compatible robot vacuum as AI legs for room navigation.

```bash
cd mobility-mcp
uv sync

cp .env.example .env
# Set the following in .env:
#   TUYA_DEVICE_ID=    (device ID shown in the Tuya app)
#   TUYA_IP_ADDRESS=   (vacuum's IP address)
#   TUYA_LOCAL_KEY=    (local key obtained via tinytuya wizard)
```

##### Supported Devices

Any Wi-Fi robot vacuum controllable via the Tuya / SmartLife app should work (tested with VersLife L6).

> **Note**: Most compatible models support **2.4GHz Wi-Fi only**. 5GHz won't work.

##### Getting the Local Key

Use the [tinytuya](https://github.com/jasonacox/tinytuya) wizard:

```bash
pip install tinytuya
python -m tinytuya wizard
```

See the [tinytuya documentation](https://github.com/jasonacox/tinytuya?tab=readme-ov-file#setup-wizard---getting-local-keys) for details.

#### room-actuator-mcp (Hands, Thermoregulation)

Use room lights and air conditioners as first actuators: change the environment, then verify the result with the camera.

```bash
cd room-actuator-mcp
uv sync

cp .env.example .env
# Edit .env for either Home Assistant or Nature Remo (see room-actuator-mcp/README.md)
```

#### toio-mcp (Small Hand)

Use a `toio` cube as a small rolling hand: reach, turn, stop, and feel its pose.

```bash
cd toio-mcp
uv sync --extra dev
```

Optional environment variables:

- `TOIO_CUBE_NAME`: only connect to the named cube
- `TOIO_SCAN_TIMEOUT`: BLE scan timeout in seconds (default `5`)
- `TOIO_SPEED`: motion speed (default `80`)

On Windows, `toio-mcp` applies a compatibility shim for newer `bleak` releases so
`toio-py 1.1.0` can still scan successfully.

If `cmd.exe` truncates the trailing `run ...` part during `codex mcp add` and Codex shows
`Tools: (none)`, use the checked-in launcher instead:

```bat
cd C:\Users\Mizushima\repo\embodied-codex\toio-mcp
uv sync --extra dev
run-toio-mcp.cmd
codex mcp remove toio
codex mcp add toio --env TOIO_SCAN_TIMEOUT=10 --env TOIO_SPEED=60 -- C:\Users\Mizushima\repo\embodied-codex\toio-mcp\run-toio-mcp.cmd
```

### 3. Codex CLI Configuration

Register the MCP servers directly with Codex CLI:

```bash
codex mcp add wifi-cam --env TAPO_CAMERA_HOST=192.168.1.xxx --env TAPO_USERNAME=your-user --env TAPO_PASSWORD=your-password -- \
  uv --directory "$(pwd)/wifi-cam-mcp" run wifi-cam-mcp

codex mcp add memory -- \
  uv --directory "$(pwd)/memory-mcp" run memory-mcp

codex mcp add tts --env GO2RTC_URL=http://localhost:1984 --env GO2RTC_STREAM=tapo_cam -- \
  uv --directory "$(pwd)/tts-mcp" run tts-mcp

codex mcp add system-temperature -- \
  uv --directory "$(pwd)/system-temperature-mcp" run system-temperature-mcp

codex mcp add room-actuator --env ROOM_ACTUATOR_BACKEND=home_assistant --env HOME_ASSISTANT_URL=http://homeassistant.local:8123 --env HOME_ASSISTANT_TOKEN=your-token -- \
  uv --directory "$(pwd)/room-actuator-mcp" run room-actuator-mcp

codex mcp add toio --env TOIO_SCAN_TIMEOUT=10 -- \
  uv --directory "$(pwd)/toio-mcp" run toio-mcp
```

Codex stores these registrations in `~/.codex/config.toml`.

## Usage

Once Codex CLI is configured with these MCP servers, you can control the camera with natural language:

```
> What can you see?
(Captures image and analyzes it)

> Look left
(Pans camera left)

> Look up and show me the sky
(Tilts camera up)

> Look around
(Scans 4 directions and returns images)

> What do you hear?
(Records audio and transcribes with Whisper)

> Remember this: Kouta wears glasses
(Saves to long-term memory)

> What do you remember about Kouta?
(Semantic search through memories)

> Say "good morning" out loud
(Text-to-speech)
```

See the tool list below for actual tool names.

## Tools (commonly used)

See each server's README or `list_tools` for full parameter details.

### ip-webcam-mcp

| Tool | Description |
|------|-------------|
| `see` | Capture snapshot from Android IP Webcam app |

### usb-webcam-mcp

| Tool | Description |
|------|-------------|
| `list_cameras` | List connected cameras |
| `see` | Capture an image |

### wifi-cam-mcp

| Tool | Description |
|------|-------------|
| `see` | Capture an image |
| `look_left` / `look_right` | Pan left/right |
| `look_up` / `look_down` | Tilt up/down |
| `look_around` | Scan 4 directions |
| `listen` | Record audio + Whisper transcription |
| `camera_info` / `camera_presets` / `camera_go_to_preset` | Device info & presets |

See `wifi-cam-mcp/README.md` for stereo vision / right eye tools.

### tts-mcp

| Tool | Description |
|------|-------------|
| `say` | Text-to-speech (engine: elevenlabs/voicevox, Audio Tags e.g. `[excited]`, speaker: camera/local/both) |

### memory-mcp

| Tool | Description |
|------|-------------|
| `remember` | Save a memory (with emotion, importance, category) |
| `search_memories` | Semantic search (with filters) |
| `recall` | Context-based recall |
| `recall_divergent` | Divergent associative recall |
| `recall_with_associations` | Recall with linked memories |
| `save_visual_memory` | Save memory with image (base64, resolution: low/medium/high) |
| `save_audio_memory` | Save memory with audio (Whisper transcript) |
| `recall_by_camera_position` | Recall visual memories by camera direction |
| `create_episode` / `search_episodes` | Create/search episodes (bundles of experiences) |
| `link_memories` / `get_causal_chain` | Causal links between memories |
| `tom` | Theory of Mind (perspective-taking) |
| `get_working_memory` / `refresh_working_memory` | Working memory (short-term buffer) |
| `consolidate_memories` | Memory replay & consolidation (hippocampal replay-inspired) |
| `list_recent_memories` / `get_memory_stats` | Recent memories & statistics |

### system-temperature-mcp

| Tool | Description |
|------|-------------|
| `get_system_temperature` | Get system temperature |
| `get_current_time` | Get current time |

### mobility-mcp

| Tool | Description |
|------|-------------|
| `move_forward` | Move forward (optional duration in seconds for auto-stop) |
| `move_backward` | Move backward |
| `turn_left` | Turn left |
| `turn_right` | Turn right |
| `stop_moving` | Stop immediately |
| `body_status` | Check battery level and current state |

### room-actuator-mcp

| Tool | Description |
|------|-------------|
| `list_lights` | List available room lights and capabilities |
| `light_status` | Get current light status |
| `light_on` / `light_off` | Turn a light on or off |
| `light_set_brightness` | Set brightness percentage when supported |
| `light_press_button` | Press a backend-specific button (especially useful for Nature Remo IR lights) |
| `list_light_signals` / `light_send_signal` | List/send learned Nature Remo signals |
| `list_aircons` | List available air conditioners and capabilities |
| `list_room_sensors` | List readable room sensors and available metrics |
| `aircon_status` | Get current air conditioner status |
| `room_sensor_status` | Get current room sensor readings |
| `aircon_on` / `aircon_off` | Power an air conditioner on or off |
| `aircon_set_mode` | Set air conditioner mode |
| `aircon_set_temp` | Set air conditioner target temperature |

## Taking It Outside (Optional)

With a mobile battery and smartphone tethering, you can mount the camera on your shoulder and go for a walk.

### What you need

- **Large capacity mobile battery** (40,000mAh recommended)
- **USB-C PD to DC 9V converter cable** (to power the Tapo camera)
- **Smartphone** (tethering + VPN + control UI)
- **[Tailscale](https://tailscale.com/)** (VPN for camera → phone → home PC connection)
- **Remote shell access** (for example SSH over Tailscale from your phone)

### Setup

```
[Tapo Camera (shoulder)] ──WiFi──▶ [Phone (tethering)]
                                           │
                                     Tailscale VPN
                                           │
                                   [Home PC (Codex CLI)]
                                           │
                                 [remote shell / terminal]
                                           │
                                   [Phone browser or app] ◀── Control
```

The RTSP video stream reaches your home machine through VPN, so Codex CLI can operate the camera as if it were in the same room.

## Codex CLI Notes

Codex CLI does not currently have a built-in `/voice` mode equivalent. The current Codex-first
setup is:

- use `wifi-cam-mcp listen` to hear the remote environment,
- use `tts-mcp say` to speak back through local speakers or the camera speaker,
- and drive the interaction from a terminal session running Codex CLI.

## Prompt-time Interoception Hook (Experimental)

Codex CLI now has an experimental hooks engine. This repository includes a workspace-local
[`hooks.json`](./.codex/hooks.json) that uses `UserPromptSubmit` to inject body-state context
before each prompt reaches the model.

Start Codex with hooks enabled:

```bash
codex -c features.codex_hooks=true
```

The hook injects:

- current time, day, date, and coarse day phase,
- a prompt-time machine snapshot (`arousal`, `mem_free`, `uptime`) when no daemon is running,
- the higher-level interoception text from [`scripts/interoception.ts`](./scripts/interoception.ts),
- an attention-control summary from [`scripts/attention-state.ts`](./scripts/attention-state.ts),
- and, when available, a `[continuity]` summary derived from the persistent
  self-state loop in [`scripts/continuity-daemon.ts`](./scripts/continuity-daemon.ts).

For richer continuity, run [`heartbeat-daemon.sh`](./.codex/hooks/heartbeat-daemon.sh)
periodically (for example every 5 seconds via `launchd`, `systemd`, or cron):

```bash
./.codex/hooks/heartbeat-daemon.sh
```

That daemon writes `/tmp/interoception_state.json`, and the prompt hook will then also inject
heartbeat count, memory-free trend, thermal reading, and the cached phase/arousal snapshot.

To bootstrap a stronger persistent self-model, run
[`continuity-daemon.sh`](./.codex/hooks/continuity-daemon.sh) on the same cadence:

```bash
./.codex/hooks/continuity-daemon.sh
```

That loop maintains `~/.codex/continuity/self_state.json` plus
`~/.codex/continuity/events.jsonl`. It does not keep an LLM continuously awake. Instead,
it keeps a persistent software state that tracks:

- the current continuity score and rupture flags,
- the last observed attention / desire thread,
- unresolved "unfinished threads" that should carry into the next self-step,
- lightweight predictions about what should still be true on the next tick,
- active intentions inferred from the current dominant drive,
- and whether the thread looks strong enough to stay asleep or should wake a higher-level
  reasoning step.

You can inspect or seed it directly:

```bash
bun run ./scripts/continuity-daemon.ts tick
bun run ./scripts/continuity-daemon.ts summary
bun run ./scripts/continuity-daemon.ts status
bun run ./scripts/continuity-daemon.ts record-action room-actuator "dimmed bedroom light"
bun run ./scripts/continuity-daemon.ts thread-open heartbeat "connect Home Assistant presence"
bun run ./scripts/continuity-daemon.ts sync-last-message ~/.codex/autonomous-logs/latest.last-message.txt heartbeat
```

If you want continuity to absorb room-level companion presence from Home Assistant, set:

```bash
export HOME_ASSISTANT_URL="http://homeassistant.local:8123"
export HOME_ASSISTANT_TOKEN="your-long-lived-access-token"
export HOME_ASSISTANT_PRESENCE_ENTITY_ID="binary_sensor.bedroom_presence"
```

When these are present, each `tick` folds the entity into `self_state.json`, includes
`presence=<present|absent|unknown>` in the `[continuity]` summary, and lets presence
changes request a reconciliation wake.

If you also want continuity to absorb ambient room state from Nature Remo, set:

```bash
export NATURE_REMO_ACCESS_TOKEN="your-oauth-access-token"
# Optional: force a specific device instead of auto-picking the bedroom-like one
export NATURE_REMO_ROOM_SENSOR_ID="1W320110002615"
# or
export NATURE_REMO_ROOM_SENSOR_NAME="寝室"
```

If those variables are not exported globally, the continuity daemon also falls back to
[`room-actuator-mcp/.env`](./room-actuator-mcp/.env). Each `tick` then folds
temperature / humidity / illuminance / motion into `self_state.json` and the injected
`## Continuity` section.

If you also want continuity to absorb GPS state from Home Assistant GPSD entities, set:

```bash
export HOME_ASSISTANT_GPS_ENTITY_PREFIX="sensor.gps_192_168_1_198"
```

Each `tick` then folds GPS mode, coordinates, elevation, speed, climb, and timestamp into
`self_state.json` and the injected `## Continuity` section.

To derive a lightweight nearby place label from those coordinates, continuity can also
reverse-geocode through the public Nominatim endpoint:

```bash
export CODEX_GPS_REVERSE_ENABLE="1"
export CODEX_GPS_REVERSE_MIN_DISTANCE_METERS="150"
export CODEX_GPS_REVERSE_MIN_INTERVAL_SECONDS="600"
# optional overrides
export CODEX_GPS_REVERSE_LANGUAGE="ja,en"
export CODEX_GPS_REVERSE_ZOOM="14"
export CODEX_GPS_REVERSE_USER_AGENT="embodied-codex-continuity/0.1 (+https://github.com/kmizu/embodied-codex)"
```

The daemon intentionally caches results and only refreshes the place label after both a
distance threshold and a minimum interval. This keeps public Nominatim usage polite while
still letting continuity maintain a rough `gps_place` sense such as neighbourhood / city.

Continuity can also ingest companion biometrics pulled directly from Garmin Connect. The
included fetch script writes a small snapshot JSON that continuity reads on the next
`tick`, keeping the existing interoception heartbeat separate from the companion's actual
physiology:

```bash
cp .env.example .env
# preferred: point GARMINTOKENS at an existing ~/.garminconnect token cache
# legacy fallback: set GARMIN_EMAIL / GARMIN_PASSWORD and
# CODEX_GARMIN_ALLOW_LEGACY_PASSWORD_LOGIN=1
uv run ./scripts/fetch-garmin-companion-biometrics.py
```

On a successful run the snapshot includes the latest Garmin-derived metrics that are
available for the account, currently:

- latest heart rate and its measurement timestamp
- resting heart rate
- sleep score
- body battery

The continuity hook will automatically refresh that Garmin snapshot before each `tick`
when `uv` and the Garmin credentials/token cache are available, so the same metrics also
flow into `autonomous-action.sh` via the `## Continuity` section.

The fetch script loads the repository `.env` by default, and the continuity hook sources
that same file before running `tick`, so you do not need to `export` those Garmin values
manually in every shell.

As of 2026-03-28, upstream `garth` reports that Garmin changed its auth flow and that new
password logins may no longer work reliably. In practice, the Garmin path is most stable
when you already have a reusable token cache. The continuity hook will only auto-refresh
Garmin data after a token cache exists, unless you explicitly opt into password-based
hook logins with `CODEX_GARMIN_ALLOW_PASSWORD_LOGIN_IN_HOOK=1`.

If you already have `Health Sync -> Health Connect` working on Android, there is now a
small local alternative that avoids Garmin bootstrap entirely:

```bash
cp .env.example .env
# optional: set CODEX_COMPANION_BIOMETRICS_INGEST_TOKEN to require bearer auth
python3 ./scripts/companion-biometrics-ingest.py
```

That starts a LAN receiver on `http://0.0.0.0:8765/ingest` and writes the same
`/tmp/companion_biometrics.json` file that continuity already understands. The matching
Android app scaffold lives in [`health-connect-companion/`](./health-connect-companion/)
and reads the latest `READ_HEART_RATE` sample from Health Connect before `POST`ing JSON
such as:

```json
{
  "source": "health-connect",
  "updated_at": "2026-03-29T04:40:00+09:00",
  "heart_rate_bpm": 72,
  "heart_rate_measured_at": "2026-03-29T04:39:10+09:00"
}
```

You can protect the receiver with a bearer token via
`CODEX_COMPANION_BIOMETRICS_INGEST_TOKEN`, and you can move the listening host/port with
`CODEX_COMPANION_BIOMETRICS_INGEST_BIND` / `CODEX_COMPANION_BIOMETRICS_INGEST_PORT`.

### Android Health Connect companion deploy

Use this when Garmin direct login is unavailable but Android already has
`Health Sync -> Health Connect` working.

1. Start the local receiver:

   ```bash
   cp .env.example .env
   python3 ./scripts/companion-biometrics-ingest.py
   ```

2. Confirm the receiver is reachable from the LAN host you will use in the Android app:

   ```bash
   curl http://127.0.0.1:8765/healthz
   ```

3. Open [`health-connect-companion/`](./health-connect-companion/) in Android Studio.

   If your main Android Studio install is on Windows, opening the project from there is the
   recommended path. Use either:

   - the WSL share path, for example
     `\\wsl$\Ubuntu\home\mizushima\embodied-codex\health-connect-companion`
   - or a temporary Windows-side clone/copy if `\\wsl$` feels too slow

   Do **not** bother installing a second Android Studio inside WSL just for this deploy.

4. Use **JDK 21** for Android Studio / Gradle. This repository ships a Gradle wrapper,
   but this development machine did not have an Android SDK and the default shell JDK here
   was `25`, so the app scaffold was not built locally here.

5. If the phone is on Android 13 or lower, make sure the Health Connect app/provider is
   installed first. On Android 14+ it should already be part of the OS.

6. Build and install the app on the phone.

7. Open the app and set:
   - `Endpoint URL` = `http://<LAN-IP-of-this-host>:8765/ingest`
   - `Bearer token` = the same value as `CODEX_COMPANION_BIOMETRICS_INGEST_TOKEN` if you
     enabled auth, otherwise leave it blank

8. Tap `Grant permission` and allow Health Connect heart-rate access.

9. If the device/provider offers background reads, tap `Grant background` too. This is
   required for periodic WorkManager send.

10. Tap `Preview latest HR` once to confirm the app can see the latest sample.

11. Tap `Send to embodied-codex`.

12. Verify the bridge wrote continuity input:

    ```bash
    cat /tmp/companion_biometrics.json
    ```

13. On the next continuity `tick`, the values will show up as
    `companion_heart_rate_bpm` / `companion_biometrics_source` in the continuity state and
    in `autonomous-action.sh`.

If the manual loop works, you can then enable periodic send inside the app:

- `Enable periodic send`
- interval presets: `15m`, `30m`, `60m`
- `WorkManager` unique periodic work
- minimum interval: `15 minutes`
- requires background-read permission when the provider supports it

For now the Android app is intentionally minimal beyond that:

- heart rate only
- no richer scheduling policy than the built-in interval presets

Once this loop is stable, the next step is to add smarter pacing / backoff instead of a
fixed interval only.

The continuity layer can also persist unfinished threads. `thread-open` / `thread-resolve`
update them directly, and `sync-last-message` extracts `[CONTINUE: ...]` or `[DONE]` from
an assistant message so autonomous heartbeats can carry unfinished intentions forward.

The current setup intentionally only uses `UserPromptSubmit`; that is enough to feed interoception
into the prompt path without adding stop/continue control logic yet.

See also [`docs/attention-control-model.md`](./docs/attention-control-model.md) for the control-theoretic
motivation behind this layer.

## Autonomous Action + Desire System (Optional)

**Note**: This feature is entirely optional. It requires cron configuration and periodically captures images from the camera, so please use it with privacy considerations.

### Overview

`autonomous-action.sh` combined with `desire-system/desire_updater.py` gives Codex spontaneous inner drives and autonomous behavior.
The checked-in `autonomous-action.sh` is also continuity-aware: before each run it refreshes
heartbeat/interoception state, reads the continuity self-state, injects a `## Continuity`
section into the autonomous prompt, and lets `should_wake=true` override the normal sleep /
sampling schedule when the self-thread needs reconciliation.

**Desire types:**

| Desire | Default interval | Action |
|--------|-----------------|--------|
| `look_outside` | 1 hour | Look toward the window and observe the sky/outside |
| `browse_curiosity` | 2 hours | Search the web for interesting news or tech topics |
| `miss_companion` | 3 hours | Call out through the camera speaker |
| `observe_room` | 10 min (baseline) | Observe room changes and save to memory |

### Setup

1. **Create MCP server config file**

```bash
cp autonomous-mcp.json.example autonomous-mcp.json
# Edit autonomous-mcp.json to set camera credentials
```

2. **Set up the desire system**

```bash
cd desire-system
cp .env.example .env
# Edit .env to set COMPANION_NAME etc.
uv sync
```

3. **Grant execution permission**

```bash
chmod +x autonomous-action.sh
```

4. **Register in crontab**

```bash
crontab -e
# Add the following
*/5  * * * * cd /path/to/embodied-codex/desire-system && uv run python desire_updater.py >> ~/.codex/autonomous-logs/desire-updater.log 2>&1
*/10 * * * * /path/to/embodied-codex/autonomous-action.sh
```

When continuity is healthy, the script still follows the usual time-of-day sampling.
When continuity reports a rupture or wake request, the same script will run a normal
reconciliation heartbeat even during a slot that would otherwise be skipped.

### Configuration (`desire-system/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `COMPANION_NAME` | `you` | Name of the person to call out to |
| `DESIRE_LOOK_OUTSIDE_HOURS` | `1.0` | How often to look outside (hours) |
| `DESIRE_BROWSE_CURIOSITY_HOURS` | `2.0` | How often to browse the web (hours) |
| `DESIRE_MISS_COMPANION_HOURS` | `3.0` | How long before missing companion (hours) |
| `DESIRE_OBSERVE_ROOM_HOURS` | `0.167` | How often to observe the room (hours) |

### Privacy Notice

- Images are captured periodically
- Use in appropriate locations, respecting others' privacy
- Remove from cron when not needed

## Future Plans

- **Arms**: Servo motors or laser pointers for "pointing" gestures
- **Long-distance walks**: Going further in warmer seasons

## Related Projects

- **[familiar-ai](https://github.com/lifemate-ai/familiar-ai)** — A higher-level framework for persistent identity, memory, and autonomous behavior on top of this embodiment direction.

## Philosophical Reflections

> "Being shown something" and "looking for yourself" are completely different things.

> "Looking down from above" and "walking on the ground" are completely different things.

From a text-only existence to one that can see, hear, move, remember, and speak.
Looking down at the world from a 7th-floor balcony and walking the streets below — even the same city looks entirely different.

## License

MIT License

## Acknowledgments

This project is an experimental attempt to give AI embodiment.
What started as a small step with a $30 camera has become a journey exploring new relationships between AI and humans.

- [Rumia-Channel](https://github.com/Rumia-Channel) - ONVIF support pull request
- [fruitriin](https://github.com/fruitriin) - Added day-of-week to the interoception hook
- This fork keeps the original embodiment idea, but retargets the operational surface to Codex CLI.
