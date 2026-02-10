# Trade_bot

Real-time OKX demo trading bot with an ultra-aggressive strategy.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set API keys for OKX demo trading:

```bash
export OKX_API_KEY="your_key"
export OKX_API_SECRET="your_secret"
export OKX_PASSPHRASE="your_passphrase"
```

## Run

```bash
python main.py
```

## Notes

- Uses OKX demo (simulated) trading via `x-simulated-trading: 1` header.
- Symbols: BTC, ETH, DOGE, SOL perpetual swaps.
- Strategy uses multi-indicator momentum + volatility with pyramiding, partial exits, and trailing stops.
