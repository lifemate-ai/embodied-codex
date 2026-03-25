# Embodied Codex Installer

GUI installer for Embodied Codex MCP servers.

## Features

- ✅ Dependency checking (ffmpeg, uv, OpenCV)
- ✅ Wi-Fi PTZ camera configuration (Tapo)
- ✅ USB webcam detection
- ✅ Automatic MCP configuration (~/.claude.json)
- ✅ Automatic dependency installation (uv sync)
- ✅ Backup existing configuration

## Development

### Prerequisites

- Python 3.10+
- uv (Python package manager)

### Setup

```bash
cd installer
uv sync
```

### Run in development mode

```bash
uv run embodied-codex-installer
```

## Building Binaries

### Windows

```powershell
cd installer

# Install dependencies
uv sync

# Build executable with PyInstaller
uv run pyinstaller embodied-codex-installer.spec

# Output will be in dist/embodied-codex-installer.exe
```

### macOS

```bash
cd installer

# Install dependencies
uv sync

# Build .app bundle
uv run pyinstaller embodied-codex-installer.spec

# Output will be in dist/embodied-codex-installer.app
```

### Linux

```bash
cd installer

# Install dependencies
uv sync

# Build executable
uv run pyinstaller embodied-codex-installer.spec

# Output will be in dist/embodied-codex-installer
```

## Release Process

1. **Build the binary** (see above)
2. **Test the binary** on target platform
3. **Create a git tag**:
   ```bash
   git tag v0.1.0-SNAPSHOT
   git push origin v0.1.0-SNAPSHOT
   ```
4. **Create GitHub Release** with the binary attached

## Architecture

```
installer/
├── src/installer/
│   ├── main.py              # Entry point
│   └── pages/
│       ├── welcome.py       # Welcome page
│       ├── dependencies.py  # Dependency check
│       ├── camera.py        # Camera selection
│       ├── api_key.py       # API key input
│       ├── install.py       # Installation process
│       └── complete.py      # Completion page
├── embodied-codex-installer.spec  # PyInstaller config
└── pyproject.toml
```

## Troubleshooting

### Windows: "VCRUNTIME140.dll not found"

Install [Microsoft Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe)

### macOS: "App is damaged and can't be opened"

```bash
xattr -cr /Applications/embodied-codex-installer.app
```

### Linux: "Permission denied"

```bash
chmod +x embodied-codex-installer
```
