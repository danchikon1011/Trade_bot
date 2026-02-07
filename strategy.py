from dataclasses import dataclass
from typing import Optional

from indicators import atr, bollinger, ema, macd, momentum, rsi, sma, trend_strength


@dataclass
class MarketSnapshot:
    close: float
    high: float
    low: float
    volume: float


@dataclass
class Signal:
    action: str
    strength: float
    reason: str


@dataclass
class PositionPlan:
    size_multiplier: float
    tp1_pct: float
    tp2_pct: float
    tp3_pct: float
    sl_pct: float


def evaluate_signal(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    volumes: list[float],
) -> Optional[Signal]:
    sma_fast = sma(closes, 50)
    sma_slow = sma(closes, 200)
    ema_20 = ema(closes, 20)
    ema_50 = ema(closes, 50)
    ema_9 = ema(closes, 9)
    bb = bollinger(closes, 20, 2.0)
    rsi_val = rsi(closes, 14)
    atr_val = atr(highs, lows, closes, 14)
    macd_val = macd(closes, 12, 26, 9)
    vol_ma = sma(volumes, 20)
    mom_5 = momentum(closes, 5)
    mom_10 = momentum(closes, 10)

    if None in (sma_fast, sma_slow, ema_20, ema_50, ema_9, bb, rsi_val, atr_val, macd_val, vol_ma):
        return None

    lower, mid, upper = bb
    _, _, macd_hist = macd_val
    trend = trend_strength(sma_fast, sma_slow)

    volume_filter = volumes[-1] > vol_ma * 0.6
    if not volume_filter:
        return None

    signal_strength = 0.0
    buy_signal = False
    high_volatility = atr_val / closes[-1] * 100 > 2.0
    ema_bullish = ema_20 > ema_50
    ema_9_above_20 = ema_9 > ema_20

    if trend == "strong_uptrend":
        if rsi_val < 65 and closes[-1] < mid * 1.03 and macd_hist > 0:
            buy_signal = True
            signal_strength = 3.0
            if ema_bullish or ema_9_above_20:
                signal_strength = 4.0
            if mom_5 and mom_5 > 2:
                signal_strength += 0.5
            if high_volatility:
                signal_strength += 0.5
        elif rsi_val < 40 and closes[-1] < lower * 1.02:
            buy_signal = True
            signal_strength = 3.5
    elif trend == "uptrend":
        if rsi_val < 58 and closes[-1] < mid * 1.02 and macd_hist > 0:
            buy_signal = True
            signal_strength = 2.5
            if ema_bullish or ema_9_above_20:
                signal_strength = 3.0
            if mom_10 and mom_10 > 2:
                signal_strength += 0.5
            if high_volatility:
                signal_strength += 0.3
    elif trend == "sideways":
        if rsi_val < 42 and closes[-1] < mid and macd_hist > 0:
            buy_signal = True
            signal_strength = 2.0
            if ema_bullish or ema_9_above_20:
                signal_strength = 2.5

    if not buy_signal:
        return None

    return Signal(action="buy", strength=signal_strength, reason=trend)


def position_plan(
    signal_strength: float,
    consecutive_wins: int,
    consecutive_losses: int,
    profit_accumulated: float,
    initial_capital: float,
    atr_val: float,
    close: float,
) -> PositionPlan:
    base_size = 1.0
    if signal_strength >= 4.5:
        base_size = 2.5
    elif signal_strength >= 4.0:
        base_size = 2.0
    elif signal_strength >= 3.5:
        base_size = 1.7
    elif signal_strength >= 3.0:
        base_size = 1.5
    elif signal_strength >= 2.5:
        base_size = 1.3
    elif signal_strength >= 2.0:
        base_size = 1.1

    if profit_accumulated > initial_capital * 0.1:
        base_size *= 1.2

    if consecutive_wins >= 4:
        base_size *= 1.4
    elif consecutive_wins >= 3:
        base_size *= 1.3
    elif consecutive_wins >= 2:
        base_size *= 1.2
    elif consecutive_losses >= 2:
        base_size *= 0.5

    position_size = min(base_size, 2.5)
    atr_multiplier = (atr_val / close) * 100
    tp1_pct = max(1.5, min(3.0, atr_multiplier * 1.2))
    tp2_pct = max(3.5, min(5.5, atr_multiplier * 2.5))
    tp3_pct = max(5.0, min(7.5, atr_multiplier * 3.5))
    sl_pct = max(1.2, min(1.8, atr_multiplier * 0.8))

    return PositionPlan(
        size_multiplier=position_size,
        tp1_pct=tp1_pct,
        tp2_pct=tp2_pct,
        tp3_pct=tp3_pct,
        sl_pct=sl_pct,
    )
