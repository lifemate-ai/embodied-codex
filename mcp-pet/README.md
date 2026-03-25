# mcp-pet — PErsonal Terminal

AIに五感を与える統合MCPサーバー。ロックマンエグゼのPET（PErsonal Terminal）から着想。

PETはネットナビ（AI）に画面・マイク・スピーカーを提供するデバイス。
mcp-pet はClaude（ネットナビ）に五感を提供する。

## できること（Phase 1: Vision）

| ツール | 説明 |
|--------|------|
| `see` | 今見えているものを撮影（source: auto/usb/onvif/skyway） |
| `look` | 視線を向ける（direction + degrees、ONVIF時のみ） |
| `look_around` | 4方向を見渡す（ONVIF時のみ） |
| `list_cameras` | 利用可能なカメラ一覧 |
| `pet_status` | PETの全センス状態を表示 |

## セットアップ

### 1. 環境変数の設定

```bash
cp .env.example .env
```

`.env` を編集：

```
# USB webcam（デフォルト有効）
PET_VISION_USB=true
PET_VISION_USB_INDEX=0

# ONVIF PTZカメラ（オプション）
PET_VISION_ONVIF_HOST=192.168.1.100
PET_VISION_ONVIF_USERNAME=your-name
PET_VISION_ONVIF_PASSWORD=your-password
```

### 2. 実行

```bash
# 依存解決
uv sync

# PTZカメラも使う場合
uv sync --extra ptz

# 起動（MCP のみ）
uv run mcp-pet

# 組み込みWebサーバー付きで起動（スマホカメラ中継）
PET_SERVER_PORT=3000 PET_SKYWAY_KEY=your-key PET_VISION_USB=false uv run mcp-pet
```

### スタンドアロンモード（組み込みWebサーバー）

`PET_SERVER_PORT` を設定すると、mcp-pet 自身がWebサーバーを起動し、
スマホからのカメラ映像を受信・保存する。外部サーバー不要で完全自己完結。

```
PET_SERVER_PORT=3000        # Webサーバーポート
PET_SKYWAY_KEY=xxx          # SkyWay APIキー（必須）
PET_SKYWAY_ROOM=mcp-pet     # ルーム名
PET_VISION_USB=false        # USBカメラ不要なら無効に
```

起動後：
- `http://localhost:3000/` — スマホで開いて「配信開始」
- `http://localhost:3000/viewer` — PCでライブ映像を視聴
- Claude Code から `see` で AI がカメラ映像を取得

## Claude Code で使う

`.mcp.json` に追加：

```json
{
  "mcpServers": {
    "pet": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/mcp-pet",
        "run",
        "mcp-pet"
      ],
      "env": {
        "PET_VISION_USB": "true"
      }
    }
  }
}
```

## アーキテクチャ

### Sense プラグイン

各センスは `Sense` ABC を実装し、独立してハードウェアの初期化・ツール提供を行う。
ハードウェアが無くてもサーバーは起動する（graceful degradation）。

```
PETServer
  ├── VisionSense
  │     ├── USB webcam (opencv)
  │     ├── ONVIF PTZ camera (optional)
  │     └── SkyWay remote camera (file read)
  └── Built-in Web Server (optional)
        ├── GET /        → client.html (スマホ配信)
        ├── GET /viewer  → viewer.html (PC視聴)
        ├── GET /config  → SkyWay設定
        └── WS  /ws      → フレーム中継
```

### Phase ロードマップ

| Phase | センス | ツール |
|-------|--------|--------|
| 1 | Vision | `see`, `look`, `look_around`, `list_cameras` |
| 2 | Hearing | `listen`（録音 + Whisper文字起こし） |
| 3 | Voice | `say`（TTS出力） |
| 4 | Proprioception | `feel`（システムセンサー） |

## テスト

```bash
uv run pytest
```

## ライセンス

MIT License
