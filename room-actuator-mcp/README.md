# room-actuator-mcp

An MCP server that gives Codex simple room-environment actuation.

Current backends:

- **Home Assistant** via the official REST API
- **Nature Remo Cloud API** for IR light appliances, air conditioners, and learned signals

This is meant to be a first "hand"-like actuator surface: change the room, then use `see` to observe the result.

## Tools

| Tool | Description |
|------|-------------|
| `list_lights` | List available lights and capabilities |
| `light_status` | Read current light status |
| `light_on` / `light_off` | Turn a light on or off |
| `light_set_brightness` | Set brightness percentage when supported |
| `light_press_button` | Press a backend-specific light button |
| `list_light_signals` | List learned Nature Remo signals for a light |
| `light_send_signal` | Send a learned Nature Remo signal by ID |
| `list_aircons` | List available air conditioners and capabilities |
| `aircon_status` | Read current air conditioner status |
| `aircon_on` / `aircon_off` | Power an air conditioner on or off |
| `aircon_set_mode` | Set air conditioner mode |
| `aircon_set_temp` | Set air conditioner target temperature |

## Setup

```bash
cd room-actuator-mcp
uv sync
cp .env.example .env
```

## Backend: Home Assistant

Set these environment variables:

```dotenv
ROOM_ACTUATOR_BACKEND=home_assistant
HOME_ASSISTANT_URL=http://homeassistant.local:8123
HOME_ASSISTANT_TOKEN=your-long-lived-access-token
HOME_ASSISTANT_VERIFY_SSL=true
```

The server uses Home Assistant's REST API on the same port as the frontend.

## Backend: Nature Remo

Set these environment variables:

```dotenv
ROOM_ACTUATOR_BACKEND=nature_remo
NATURE_REMO_ACCESS_TOKEN=your-oauth-access-token
NATURE_REMO_API_BASE_URL=https://api.nature.global
```

`LIGHTING_BACKEND` is still accepted as a compatibility fallback, but new setups should use
`ROOM_ACTUATOR_BACKEND`.

The current implementation uses the **cloud** API. That is enough to drive real IR light appliances, air conditioners, and learned signals, but it is still one-way IR control, so the camera should verify the result.

Nature's developer docs also expose a Local API reference for same-LAN access, but that is **not implemented here yet**.

## Codex CLI registration

### Home Assistant

```bash
codex mcp add room-actuator \
  --env ROOM_ACTUATOR_BACKEND=home_assistant \
  --env HOME_ASSISTANT_URL=http://homeassistant.local:8123 \
  --env HOME_ASSISTANT_TOKEN=your-token -- \
  uv --directory "$(pwd)/room-actuator-mcp" run room-actuator-mcp
```

### Nature Remo

```bash
codex mcp add room-actuator \
  --env ROOM_ACTUATOR_BACKEND=nature_remo \
  --env NATURE_REMO_ACCESS_TOKEN=your-token -- \
  uv --directory "$(pwd)/room-actuator-mcp" run room-actuator-mcp
```

## Usage examples

- "List the lights you can control"
- "Turn on the ceiling light"
- "Set the desk light to 20%"
- "Press the night button on the room light"
- "Send the learned warm-light signal"
- "List the air conditioners you can control"
- "Turn on the bedroom air conditioner"
- "Set the bedroom air conditioner to warm mode"
- "Set the bedroom air conditioner to 23 degrees"

## Testing

```bash
uv sync --extra dev
uv run ruff check .
uv run python -m pytest -v
```
