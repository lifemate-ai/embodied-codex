# WiFi Camera MCP Server

Tapo C210などのWiFiカメラをMCP経由で制御して、AIに部屋を見渡してもらうためのサーバー。

## 対応カメラ

- TP-Link Tapo C210 (3MP)
- TP-Link Tapo C220 (4MP)
- その他Tapoシリーズのパン・チルト対応カメラ

## できること

| ツール | 説明 |
|--------|------|
| `camera_capture` | 今見えてる景色を撮影 |
| `camera_pan_left` | 左を向く |
| `camera_pan_right` | 右を向く |
| `camera_tilt_up` | 上を向く |
| `camera_tilt_down` | 下を向く |
| `camera_look_around` | 部屋を見渡す（4方向撮影） |
| `camera_info` | カメラ情報取得 |
| `camera_presets` | プリセット位置一覧 |
| `camera_go_to_preset` | プリセット位置に移動 |

## セットアップ

### 複数の場所のカメラを使う

MCP は `wifi-cam` の1件だけ登録する。台数に固定上限はなく、カメラの追加は
リポジトリ直下の `wifi-cameras.toml` に書く。MCP の設定を台数分増やす必要はない。
実際に同時利用できる台数はネットワークや機器、PC の処理能力による。

1. [`../wifi-cameras.toml.example`](../wifi-cameras.toml.example) を
   リポジトリ直下の `wifi-cameras.toml` にコピーする。
2. `outside`（外）、`inside`（室内）、`bedside`（ベッド脇）の `host` を実機のIPに変更する。
   不要なカメラのテーブルは削除し、必要なら `[cameras.新しいID]` を追加する。
3. 各カメラの `username` / `password` に、カメラのアカウント情報を直接書く。
   IPと認証情報をこのファイルだけで管理でき、`.env` は不要。
4. Codex の Wi-Fi カメラ MCP を再起動する。設定変更は起動時に読み込む。

```toml
default_camera = "inside"

[cameras.outside]
host = "192.168.1.100"
username = "your-camera-user"
password = "your-camera-password"
mount_mode = "normal"

[cameras.inside]
host = "192.168.1.101"
username = "your-camera-user"
password = "your-camera-password"
mount_mode = "ceiling"
```

```text
camera_list()
see(camera_id="outside")
camera_capture(camera_id="bedside")
look_left(camera_id="inside", degrees=30)
listen(camera_id="outside", duration=5)
```

`camera_id` を省略すると `default_camera` を使う。省略時に別の接続済みカメラへ
自動で切り替えることはない。`camera_list` で各IDと接続処理の状態
（`connecting` / `connected` / `offline`）を確認できる。
カメラ接続はバックグラウンドで進むため、接続待ちの間も一覧を取得できる。
`connected` は起動時の接続成功を表し、継続的な死活監視ではない。
1台が接続に失敗してもサーバーとほかのカメラは利用できる。失敗した台は接続を確認して再起動する。
起動時に接続できた台の、その後の通信断は既存の再接続処理で扱う。

カメラIDは英数字・`_`・`-`（先頭は英数字）。各台に `mount_mode`、`onvif_port`、
`max_width`、`max_height`、`stream_url_env` を設定できる。
名前付きカメラの設置方向はこのファイルの指定を使い、`mcpBehavior.toml` の共通 `mount_mode`
には影響されない。撮影・録音は `CAPTURE_DIR/<camera_id>/` に分けて保存する。
`wifi-cameras.toml` は Git 管理対象外。

環境変数で管理したい場合は `username` / `password` の代わりに
`username_env` / `password_env` で変数名を指定する方式も使える。
両方書いた場合は直接指定を優先する。空文字や文字列以外の直接指定は設定エラーになる。
パスワードに `\` が含まれる場合は、TOMLのリテラル文字列（例: `password = 'abc\def'`）を使える。

左右ペアを使う場合は、ファイル先頭に `stereo_pair = ["leftのID", "rightのID"]` を指定する。
`see_both` など既存の両眼ツールを使え、呼び出し時に
`left_camera_id` / `right_camera_id` で別のペアも選べる。
別々の場所のカメラをペア指定しただけでは、距離推定用のステレオ校正にはならない。

チェックアウト内では上記ファイルを自動検出する。別の場所のファイルは
`WIFI_CAMERAS_TOML` にパスを指定する。
ファイルがない場合は従来の `TAPO_*` / `TAPO_RIGHT_*` 設定を使い、IDは `primary` / `right` になる。
明示したファイルの不在、設定ミス、必要な認証変数の不在は起動エラーとして通知する。

### 1. カメラの初期設定（Tapoアプリ）

1. スマホに「TP-Link Tapo」アプリをインストール
2. Tapoアカウントを作成（メールアドレスとパスワード）
3. アプリから「デバイスを追加」→ カメラを選択
4. カメラの電源を入れ、アプリの指示に従ってWiFi接続

### 2. カメラのIPアドレスを調べる

以下のいずれかの方法で確認：

| 方法 | 手順 |
|------|------|
| **Tapoアプリ** | カメラ設定 → デバイス情報 → IPアドレス |
| **ルーター管理画面** | 接続機器一覧から「Tapo_C210」等を探す |
| **nmapコマンド** | `nmap -sn 192.168.1.0/24` |

> **Tips**: ルーターでDHCP予約（IP固定）を設定しておくと、カメラ再起動後もIPアドレスが変わらず便利です

### 3. カメラのアカウントを作る

1. Tapoアプリ -> ホーム ->  (カメラ名)を選択 -> 右上の歯車アイコンをタップ -> 「高度な設定」をタップ
2. 「カメラのアカウント」がオフになっているのでタップ -> 「カメラのアカウント」オン -> 「アカウント情報」
3. カメラのアカウントのユーザー名（user-name）とパスワード（user-password）を設定（後で使う）
  - ローカルのアカウントでTP-Linkのアカウントとは無関係なので注意

### 4. 環境変数の設定

```bash
cp .env.example .env
```

`.env` を編集：

```
TAPO_CAMERA_HOST=192.168.1.100    # カメラのIPアドレス
TAPO_USERNAME=your-name     # Tapoカメラ（TP-Linkアカウントではない）のユーザー名
TAPO_PASSWORD=your-password # Tapoカメラ（TP-Linkアカウントではない）のパスワード
```

---

### 5. 実行

#### 依存関係のインストール

```bash
uv sync
```

#### 動作確認

```bash
uv run wifi-cam-mcp
```

## Claude Desktopで使う

`claude_desktop_config.json`  または適切な設定ファイルに追加：

### Python版

```json
{
  "mcpServers": {
    "wifi-cam": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/wifi-cam-mcp",
        "run",
        "wifi-cam-mcp"
      ],
      "env": {
        "TAPO_CAMERA_HOST": "192.168.1.100",
        "TAPO_USERNAME": "your-name",
        "TAPO_PASSWORD": "your-password"
      }
    }
  }
}
```

## Claude Codeで使う

`.mcp.json` をプロジェクトルートまたはホームディレクトリに作成：

### Python版

```json
{
  "mcpServers": {
    "wifi-cam": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/wifi-cam-mcp",
        "run",
        "wifi-cam-mcp"
      ],
      "env": {
        "TAPO_CAMERA_HOST": "192.168.1.100",
        "TAPO_USERNAME": "your-name",
        "TAPO_PASSWORD": "your-password"
      }
    }
  }
}
```

## 使用例

Claudeに話しかける：

- 「今カメラに何が映ってる？」
- 「ちょっと左を見て」
- 「部屋全体を見渡して」
- 「窓は開いてる？」

## テスト

### Python版

```bash
uv run pytest
```

## トラブルシューティング

### カメラに接続できない

- カメラとPCが同じネットワーク上にあるか確認
- IPアドレスが正しいか確認（Tapoアプリで再確認）
- ファイアウォールが通信をブロックしていないか確認

### 認証エラー

- カメラアカウントのメールアドレスとパスワードが正しいか確認

### 画像が取得できない

- カメラのファームウェアを最新に更新
- カメラを再起動

## 注意事項

- **Python版**: pytapoは非公式ライブラリのため、TP-Linkの仕様変更で動作しなくなる可能性があります
- カメラはローカルネットワーク内からのみアクセス可能です
- 認証情報（.envファイル）は絶対にGitにコミットしないでください

## ライセンス

MIT License
