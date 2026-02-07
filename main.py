import asyncio
import logging
import os
from collections import deque
from typing import Dict, List

from engine import TradeEngine
from okx_client import OkxCredentials, OkxRestClient
from okx_ws import OkxWebsocket

logging.basicConfig(level=logging.INFO)


SYMBOLS = [
    "BTC-USDT-SWAP",
    "ETH-USDT-SWAP",
    "DOGE-USDT-SWAP",
    "SOL-USDT-SWAP",
]


class MarketState:
    def __init__(self, maxlen: int = 500) -> None:
        self.closes = deque(maxlen=maxlen)
        self.highs = deque(maxlen=maxlen)
        self.lows = deque(maxlen=maxlen)
        self.volumes = deque(maxlen=maxlen)

    def append(self, candle: Dict[str, float]) -> None:
        self.closes.append(candle["close"])
        self.highs.append(candle["high"])
        self.lows.append(candle["low"])
        self.volumes.append(candle["volume"])

    def as_lists(self) -> Dict[str, List[float]]:
        return {
            "closes": list(self.closes),
            "highs": list(self.highs),
            "lows": list(self.lows),
            "volumes": list(self.volumes),
        }


async def run_symbol(inst_id: str, client: OkxRestClient, base_size: float) -> None:
    state = MarketState()
    engine = TradeEngine(client=client, inst_id=inst_id, initial_capital=10000, base_size=base_size)
    ws = OkxWebsocket(url="wss://ws.okx.com:8443/ws/v5/public", inst_id=inst_id, bar="1m")

    async def handler(candle: Dict[str, float]) -> None:
        state.append(candle)
        if len(state.closes) < 210:
            return
        await engine.on_candle(candle, state.as_lists())

    await ws.connect(handler)


async def main() -> None:
    creds = OkxCredentials(
        api_key=os.environ["OKX_API_KEY"],
        api_secret=os.environ["OKX_API_SECRET"],
        passphrase=os.environ["OKX_PASSPHRASE"],
    )
    client = OkxRestClient(creds=creds, base_url="https://www.okx.com", simulated=True)

    tasks = [
        asyncio.create_task(run_symbol(inst_id, client, base_size=0.01)) for inst_id in SYMBOLS
    ]
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
