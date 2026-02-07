import asyncio
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional

from indicators import atr, bollinger, ema, macd, rsi
from okx_client import OkxRestClient
from strategy import PositionPlan, Signal, evaluate_signal, position_plan


@dataclass
class Position:
    entry_price: float
    entry_time: float
    size_multiplier: float
    signal_strength: float
    tp1_price: float
    tp2_price: float
    tp3_price: float
    sl_price: float
    tp1_hit: bool = False
    tp2_hit: bool = False
    trailing_stop: Optional[float] = None
    pyramid_count: int = 0


class TradeEngine:
    def __init__(
        self,
        client: OkxRestClient,
        inst_id: str,
        initial_capital: float,
        base_size: float,
    ) -> None:
        self._client = client
        self._inst_id = inst_id
        self._capital = initial_capital
        self._initial_capital = initial_capital
        self._base_size = base_size
        self._position: Optional[Position] = None
        self._consecutive_wins = 0
        self._consecutive_losses = 0
        self._profit_accumulated = 0.0
        self._lock = asyncio.Lock()

    async def on_candle(self, candle: Dict[str, float], state: Dict[str, List[float]]) -> None:
        async with self._lock:
            closes = state["closes"]
            highs = state["highs"]
            lows = state["lows"]
            volumes = state["volumes"]

            signal = evaluate_signal(closes, highs, lows, volumes)
            if self._position is None and signal:
                await self._open_position(signal, closes, highs, lows)
            elif self._position is not None:
                await self._manage_position(candle["close"], closes, highs, lows)

    async def _open_position(self, signal: Signal, closes: List[float], highs: List[float], lows: List[float]) -> None:
        atr_val = atr(highs, lows, closes, 14)
        if atr_val is None:
            return
        plan = position_plan(
            signal_strength=signal.strength,
            consecutive_wins=self._consecutive_wins,
            consecutive_losses=self._consecutive_losses,
            profit_accumulated=self._profit_accumulated,
            initial_capital=self._initial_capital,
            atr_val=atr_val,
            close=closes[-1],
        )
        size_multiplier = plan.size_multiplier
        order_size = self._base_size * size_multiplier
        await self._client.place_order(
            inst_id=self._inst_id,
            side="buy",
            ord_type="market",
            sz=str(order_size),
            td_mode="cross",
        )
        entry_price = closes[-1]
        self._position = Position(
            entry_price=entry_price,
            entry_time=asyncio.get_event_loop().time(),
            size_multiplier=size_multiplier,
            signal_strength=signal.strength,
            tp1_price=entry_price * (1 + plan.tp1_pct / 100),
            tp2_price=entry_price * (1 + plan.tp2_pct / 100),
            tp3_price=entry_price * (1 + plan.tp3_pct / 100),
            sl_price=entry_price * (1 - plan.sl_pct / 100),
        )

    async def _manage_position(self, current_price: float, closes: List[float], highs: List[float], lows: List[float]) -> None:
        position = self._position
        if position is None:
            return

        if position.pyramid_count == 0 and position.signal_strength >= 3.0:
            if current_price >= position.entry_price * 1.005:
                position.size_multiplier *= 1.4
                position.pyramid_count = 1
        if position.pyramid_count == 1 and position.signal_strength >= 3.5:
            if current_price >= position.entry_price * 1.015:
                position.size_multiplier *= 1.3
                position.pyramid_count = 2

        if current_price >= position.tp1_price and not position.tp1_hit:
            position.tp1_hit = True
            position.trailing_stop = current_price * 0.992
            await self._partial_exit(current_price, 0.2, reason="TP1_PARTIAL_20")
            return

        if current_price >= position.tp2_price and position.tp1_hit and not position.tp2_hit:
            position.tp2_hit = True
            position.trailing_stop = current_price * 0.990
            await self._partial_exit(current_price, 0.3, reason="TP2_PARTIAL_30")
            return

        if position.trailing_stop is not None:
            trailing = current_price * (0.990 if position.tp2_hit else 0.992)
            if trailing > position.trailing_stop:
                position.trailing_stop = trailing

        exit_reason = None
        if position.trailing_stop and current_price <= position.trailing_stop:
            exit_reason = "TRAILING_STOP"
        elif current_price >= position.tp3_price:
            exit_reason = "TP3_FULL"
        elif current_price <= position.sl_price:
            exit_reason = "SL"
        else:
            rsi_val = rsi(closes, 14)
            bb = bollinger(closes, 20, 2.0)
            if rsi_val and rsi_val > 78:
                exit_reason = "RSI_EXTREME"
            elif bb and current_price > bb[2] * 1.02:
                exit_reason = "BB_EXTREME"

        if exit_reason:
            await self._close_position(current_price, exit_reason)

    async def _partial_exit(self, current_price: float, fraction: float, reason: str) -> None:
        position = self._position
        if position is None:
            return
        exit_size = self._base_size * position.size_multiplier * fraction
        await self._client.place_order(
            inst_id=self._inst_id,
            side="sell",
            ord_type="market",
            sz=str(exit_size),
            td_mode="cross",
            reduce_only=True,
            cl_ord_id=f"exit-{uuid.uuid4().hex[:10]}",
        )
        pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
        pnl_amount = self._capital * (pnl_pct / 100) * fraction * position.size_multiplier
        self._capital += pnl_amount
        self._profit_accumulated += max(0.0, pnl_amount)

    async def _close_position(self, current_price: float, reason: str) -> None:
        position = self._position
        if position is None:
            return
        if position.tp2_hit:
            fraction = 0.5
        elif position.tp1_hit:
            fraction = 0.8
        else:
            fraction = 1.0
        exit_size = self._base_size * position.size_multiplier * fraction
        await self._client.place_order(
            inst_id=self._inst_id,
            side="sell",
            ord_type="market",
            sz=str(exit_size),
            td_mode="cross",
            reduce_only=True,
            cl_ord_id=f"close-{uuid.uuid4().hex[:10]}",
        )
        pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
        pnl_amount = self._capital * (pnl_pct / 100) * fraction * position.size_multiplier
        self._capital += pnl_amount
        self._profit_accumulated += max(0.0, pnl_amount)

        if pnl_pct > 0:
            self._consecutive_wins += 1
            self._consecutive_losses = 0
        else:
            self._consecutive_losses += 1
            self._consecutive_wins = 0
        self._position = None
