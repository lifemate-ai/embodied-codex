"""Built-in web server for mcp-pet frame relay and SkyWay support."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from pathlib import Path
from typing import Any

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from .config import ServerConfig

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


class FrameRelay:
    """Receives base64 JPEG frames via WebSocket, saves to disk."""

    def __init__(self, frames_dir: str, save_interval: float = 10.0) -> None:
        self._frames_dir = Path(frames_dir)
        self._save_interval = save_interval
        self._last_save: dict[str, float] = {}
        self._frames_dir.mkdir(parents=True, exist_ok=True)

    async def handle_frame(self, ws_id: str, jpeg_b64: str) -> dict[str, Any] | None:
        """Process an incoming frame. Returns save info if frame was saved."""
        now = time.time()
        last = self._last_save.get(ws_id, 0)

        if now - last < self._save_interval:
            return None

        self._last_save[ws_id] = now
        buf = base64.b64decode(jpeg_b64)

        ts = time.strftime("%Y-%m-%dT%H-%M-%S")
        latest_path = self._frames_dir / "latest.jpg"
        snap_path = self._frames_dir / f"{ts}.jpg"

        loop = asyncio.get_event_loop()
        await asyncio.gather(
            loop.run_in_executor(None, latest_path.write_bytes, buf),
            loop.run_in_executor(None, snap_path.write_bytes, buf),
        )

        logger.info("Frame saved: %s", snap_path)
        return {"type": "saved", "timestamp": ts}

    def remove_client(self, ws_id: str) -> None:
        self._last_save.pop(ws_id, None)


def create_web_app(config: ServerConfig, frames_dir: str) -> Starlette:
    """Create the Starlette ASGI application."""

    relay = FrameRelay(frames_dir, save_interval=config.save_interval)

    async def client_page(request: Request) -> HTMLResponse:
        html = (STATIC_DIR / "client.html").read_text(encoding="utf-8")
        return HTMLResponse(html)

    async def viewer_page(request: Request) -> HTMLResponse:
        html = (STATIC_DIR / "viewer.html").read_text(encoding="utf-8")
        return HTMLResponse(html)

    async def config_endpoint(request: Request) -> JSONResponse:
        return JSONResponse({
            "skywayKey": config.skyway_key,
            "roomName": config.skyway_room,
        })

    async def ws_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        ws_id = str(id(websocket))
        logger.info("WebSocket client connected: %s", ws_id)

        await websocket.send_json({
            "type": "connected",
            "message": "PET中継モードで接続しました。カメラを向けてください",
            "mode": "relay",
        })

        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                if data.get("type") != "frame" or not isinstance(data.get("jpeg"), str):
                    continue

                result = await relay.handle_frame(ws_id, data["jpeg"])
                if result:
                    await websocket.send_json(result)
        except WebSocketDisconnect:
            pass
        finally:
            relay.remove_client(ws_id)
            logger.info("WebSocket client disconnected: %s", ws_id)

    routes = [
        Route("/", client_page),
        Route("/viewer", viewer_page),
        Route("/config", config_endpoint),
        WebSocketRoute("/ws", ws_endpoint),
    ]

    return Starlette(routes=routes)


async def run_web_server(config: ServerConfig, frames_dir: str) -> None:
    """Run the built-in web server (call as asyncio task)."""
    app = create_web_app(config, frames_dir)
    uv_config = uvicorn.Config(
        app,
        host=config.host,
        port=config.port,
        log_level="info",
    )
    server = uvicorn.Server(uv_config)
    # Don't let uvicorn steal signal handlers (MCP stdio manages the process)
    server.install_signal_handlers = lambda: None
    await server.serve()
