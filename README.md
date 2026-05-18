# Focus Traders Weekly EM
# Credits to Claude Code without which this project will not be possible
  

A standalone trading dashboard for tracking weekly expected moves across 30+ tickers.

## Files

| File | Description |
|------|-------------|
| `focus-traders-em.html` | Main dashboard — open in browser |
| `focus_traders_server.py` | Python backend (yfinance + Flask) |
| `start_server.bat` | One-click launcher for the Python server |

## Quick Start

### Option A — With Python server (recommended)
1. Double-click `start_server.bat`
2. Browser opens automatically at `http://localhost:5000`

### Option B — Without Python (CORS proxy fallback)
1. Open `focus-traders-em.html` directly in your browser

## Dependencies (auto-installed by start_server.bat)
`pip install flask yfinance reportlab pandas numpy`

## Features
- Custom calendar date picker (Fridays highlighted in gold)
- Auto-fetches Friday Closing Price + Expected Move (ATM straddle)
- Low / High calculated automatically (FCP +/- EM)
- Click-to-edit EM and FCP for manual overrides (ES, NQ, etc.)
- PDF and CSV export
- 30+ tickers with section grouping (FUTURES, LEAPS, ON RADAR)
- Dark trading terminal theme

## Ticker Notes
- Use `^SPX` for SPX options EM (not `^GSPC`)
- `ES=F` and `NQ=F` FCP auto-fetches; EM requires manual entry
