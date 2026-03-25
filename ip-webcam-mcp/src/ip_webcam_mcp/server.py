"""Android IP Webcam アプリ用 MCP サーバー。"""

import asyncio
import base64
import os
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    ImageContent,
    TextContent,
    Tool,
)

from ._behavior import get_behavior


server = Server("ip-webcam-mcp")

# 環境変数から設定を読み取る（シークレット）
HOST = os.environ.get("IP_WEBCAM_HOST", "")
USERNAME = os.environ.get("IP_WEBCAM_USERNAME", "")
PASSWORD = os.environ.get("IP_WEBCAM_PASSWORD", "")

# 行動設定のデフォルト（TOML > env > default）
_DEFAULT_PORT = os.environ.get("IP_WEBCAM_PORT", "8080")


def get_base_url() -> str:
    """ベース URL を返す。HOST が未設定の場合は例外を投げる。"""
    if not HOST:
        raise RuntimeError("環境変数 IP_WEBCAM_HOST が設定されていません")
    port = get_behavior("ip-webcam", "port", _DEFAULT_PORT)
    return f"http://{HOST}:{port}"


def get_auth() -> httpx.BasicAuth | None:
    """Basic 認証情報を返す。未設定の場合は None。"""
    if USERNAME and PASSWORD:
        return httpx.BasicAuth(USERNAME, PASSWORD)
    return None


@server.list_tools()
async def list_tools() -> list[Tool]:
    """利用可能なツール一覧を返す。"""
    return [
        Tool(
            name="see",
            description=(
                "Android IP Webcam アプリから画像をキャプチャする。"
                "スマートフォンのカメラが捉えた映像を見るための目として機能する。"
                "base64 エンコードされた JPEG 画像を返す。"
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent | ImageContent]:
    """ツール呼び出しを処理する。"""
    if name == "see":
        try:
            # /shot.jpg エンドポイントからスナップショットを取得
            url = f"{get_base_url()}/shot.jpg"
            auth = get_auth()
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, auth=auth)
                response.raise_for_status()

            image_base64 = base64.b64encode(response.content).decode("utf-8")
            return [
                ImageContent(
                    type="image",
                    data=image_base64,
                    mimeType="image/jpeg",
                )
            ]
        except RuntimeError as e:
            return [TextContent(type="text", text=f"エラー: {e}")]
        except httpx.HTTPError as e:
            return [TextContent(type="text", text=f"HTTP エラー: {e}")]

    return [TextContent(type="text", text=f"未知のツール: {name}")]


async def run_server():
    """MCP サーバーを起動する。"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main():
    """エントリーポイント。"""
    try:
        import jurigged
        jurigged.watch(pattern="src/**/*.py", logger=None)
    except ImportError:
        pass
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
