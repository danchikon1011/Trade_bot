import asyncio
import json
import logging
from typing import Any, Callable, Dict

import websockets

logger = logging.getLogger(__name__)


class OkxWebsocket:
    def __init__(self, url: str, inst_id: str, bar: str = "1m") -> None:
        self._url = url
        self._inst_id = inst_id
        self._bar = bar
        self._running = False

    async def connect(self, handler: Callable[[Dict[str, Any]], asyncio.Future]) -> None:
        self._running = True
        backoff = 1
        while self._running:
            try:
                async with websockets.connect(self._url, ping_interval=20, ping_timeout=10) as ws:
                    await ws.send(
                        json.dumps(
                            {
                                "op": "subscribe",
                                "args": [
                                    {"channel": "candle" + self._bar, "instId": self._inst_id}
                                ],
                            }
                        )
                    )
                    backoff = 1
                    async for msg in ws:
                        data = json.loads(msg)
                        if "event" in data:
                            continue
                        if "data" not in data:
                            continue
                        for candle in data["data"]:
                            await handler(self._parse_candle(candle))
            except Exception as exc:
                logger.warning("Websocket error: %s", exc)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)

    def stop(self) -> None:
        self._running = False

    @staticmethod
    def _parse_candle(candle: list[str]) -> Dict[str, float]:
        return {
            "ts": float(candle[0]),
            "open": float(candle[1]),
            "high": float(candle[2]),
            "low": float(candle[3]),
            "close": float(candle[4]),
            "volume": float(candle[5]),
        }
