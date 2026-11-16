# F.O.C.U.S.© Traders Weekly EM

**Jachbit 2026** · **Open it online:** https://jachbit.github.io/focus-traders-em/

Credits to Claude Code without which this project will not be possible

A standalone trading dashboard for tracking weekly expected moves across 30+ tickers.

## Files

| File | Description |
|------|-------------|
| `focus-traders-em.html` | Main dashboard — open in browser |
| `focus_traders_server.py` | Python backend (yfinance + Flask) |
| `start_server.bat` | One-click launcher for the Python server |
| `em_build.py` | Builds `data/em.json` for the online page (runs the server's own yFinance EM / FCP / MMM code) |
| `tickers.txt` | Tickers for the online page, one per line |
| `.github/workflows/em.yml` | Runs `em_build.py` every market hour on GitHub and saves `data/em.json` |
| `index.html` | Sends the GitHub Pages address on to `focus-traders-em.html` |

## Quick Start

### Option A — With Python server (recommended)
1. Double-click `start_server.bat`
2. Browser opens automatically at `http://localhost:5000`

### Option B — Online, no Python (GitHub Pages)
1. Open https://jachbit.github.io/focus-traders-em/
2. The numbers come from yFinance every market hour (weekdays, about 9:30 AM - 4 PM ET), run on GitHub by `em_build.py` with the same math as the server; the header shows when (e.g. "Online data (yFinance) · 2026-11-16 10:35 ET").
3. To add or remove a ticker online, edit `tickers.txt` on GitHub; it is picked up on the next run (Actions tab → EM data → Run workflow to run it now).
4. The last 13 Fridays' closes are kept, so the date picker works for recent Fridays; EM / +MMM are for the week the latest run covers.
5. PDF: the ↓ PDF button opens the print box (pick Save as PDF): white, ink-saving, named `FOCUS_Traders_EM_<timestamp>`.

## Dependencies (auto-installed by start_server.bat)
`pip install flask yfinance reportlab pandas numpy`

## Features
- Custom calendar date picker (Fridays highlighted in gold)
- Auto-fetches Friday Closing Price + Expected Move (Spot × ATM IV × √(DTE/365)) + MMM on earnings weeks
- Low / High calculated automatically (FCP +/- EM)
- Click-to-edit EM and FCP for manual overrides (ES, NQ, etc.)
- PDF and CSV export
- 30+ tickers with section grouping (FUTURES, LEAPS, ON RADAR)
- Dark trading terminal theme

## Ticker Notes
- Use `^SPX` for SPX options EM (not `^GSPC`)
- `ES=F` and `NQ=F` FCP auto-fetches; EM requires manual entry

For personal research only, not financial advice. © 2026 Jachbit. All rights reserved. · [linktr.ee/jachbit](https://linktr.ee/jachbit)
