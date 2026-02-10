from collections import deque
from dataclasses import dataclass
from typing import Deque, List, Optional, Tuple

import numpy as np


@dataclass
class IndicatorState:
    closes: Deque[float]
    highs: Deque[float]
    lows: Deque[float]
    volumes: Deque[float]


def ema(values: List[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    alpha = 2 / (period + 1)
    ema_val = values[0]
    for value in values[1:]:
        ema_val = alpha * value + (1 - alpha) * ema_val
    return ema_val


def ema_series(values: List[float], period: int) -> List[float]:
    if len(values) < period:
        return []
    alpha = 2 / (period + 1)
    ema_vals = [values[0]]
    for value in values[1:]:
        ema_vals.append(alpha * value + (1 - alpha) * ema_vals[-1])
    return ema_vals


def sma(values: List[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    return float(np.mean(values[-period:]))


def rsi(values: List[float], period: int = 14) -> Optional[float]:
    if len(values) < period + 1:
        return None
    deltas = np.diff(values[-(period + 1) :])
    gains = np.maximum(deltas, 0)
    losses = np.maximum(-deltas, 0)
    avg_gain = np.mean(gains)
    avg_loss = np.mean(losses)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    trs = []
    for i in range(1, period + 1):
        high = highs[-i]
        low = lows[-i]
        prev_close = closes[-i - 1]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
    return float(np.mean(trs))


def bollinger(values: List[float], period: int = 20, std_mult: float = 2.0) -> Optional[Tuple[float, float, float]]:
    if len(values) < period:
        return None
    window = np.array(values[-period:])
    mid = float(np.mean(window))
    std = float(np.std(window))
    upper = mid + std_mult * std
    lower = mid - std_mult * std
    return lower, mid, upper


def macd(values: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Optional[Tuple[float, float, float]]:
    if len(values) < slow + signal:
        return None
    fast_ema = ema_series(values, fast)
    slow_ema = ema_series(values, slow)
    if not fast_ema or not slow_ema:
        return None
    min_len = min(len(fast_ema), len(slow_ema))
    macd_line = np.array(fast_ema[-min_len:]) - np.array(slow_ema[-min_len:])
    signal_line = ema_series(macd_line.tolist(), signal)
    if not signal_line:
        return None
    hist = macd_line[-1] - signal_line[-1]
    return float(macd_line[-1]), float(signal_line[-1]), float(hist)


def trend_strength(sma_fast: Optional[float], sma_slow: Optional[float]) -> str:
    if sma_fast is None or sma_slow is None:
        return "unknown"
    diff_pct = ((sma_fast - sma_slow) / sma_slow) * 100
    if diff_pct > 3:
        return "strong_uptrend"
    if diff_pct > 1:
        return "uptrend"
    if diff_pct < -3:
        return "strong_downtrend"
    if diff_pct < -1:
        return "downtrend"
    return "sideways"


def momentum(values: List[float], period: int) -> Optional[float]:
    if len(values) < period + 1:
        return None
    return ((values[-1] - values[-period - 1]) / values[-period - 1]) * 100
