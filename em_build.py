#!/usr/bin/env python3
"""
F.O.C.U.S.(c) Traders Weekly EM - data build for the GitHub Pages version.  Jachbit 2026

Runs every market hour in GitHub Actions (.github/workflows/em.yml) and writes data/em.json,
which focus-traders-em.html reads when no local Python server is running.

The numbers come from focus_traders_server.py itself: this script calls the server's own
/api/em and /api/quote endpoints in-process (Flask test client, no web server started), so the
online EM / MMM / Friday close are exactly what start_server.bat gives on the PC.

  EM  = Spot x ATM IV x sqrt(DTE / 365), expiry nearest the next Friday
  MMM = ATM straddle of the expiry nearest earnings, when earnings fall in that week
  FCP = Friday closing price (the last 13 Fridays are saved for the date picker)

Tickers: tickers.txt (one per line, # = comment).  Run locally: python em_build.py
"""

import json, pathlib, sys, time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import focus_traders_server as srv

HERE    = pathlib.Path(__file__).resolve().parent
OUT     = HERE / "data" / "em.json"
ET      = ZoneInfo("America/New_York")
FRIDAYS = 13


def base_friday(now_et):
    """Most recent Friday whose close is in: today after 4 PM ET on a Friday, else the Friday before."""
    d = now_et.date()
    back = (d.weekday() - 4) % 7
    if back == 0 and now_et.hour < 16:
        back = 7
    return d - timedelta(days=back)


def read_tickers():
    out = []
    for line in (HERE / "tickers.txt").read_text(encoding="utf-8").splitlines():
        t = line.split("#", 1)[0].strip().upper()
        if t and t not in out:
            out.append(t)
    return out


def call(client, path, **params):
    r = client.get(path, query_string=params)
    data = r.get_json(silent=True) or {}
    if r.status_code != 200:
        raise RuntimeError(data.get("error") or f"HTTP {r.status_code}")
    return data


def main():
    now_et  = datetime.now(ET)
    base    = base_friday(now_et)
    fridays = [base - timedelta(days=7 * i) for i in range(FRIDAYS)]
    client  = srv.app.test_client()
    tickers = read_tickers()
    rows, ok, failed = {}, 0, 0

    for sym in tickers:
        row = {"company": srv._DISPLAY_NAMES.get(sym, sym)}
        try:
            em = call(client, "/api/em", symbol=sym, date=base.isoformat())
            row.update(em=em["em"], iv=em["iv"], expiry=em["expiry"], atm_strike=em["atm_strike"],
                       current_price=em["current_price"], mmm=em.get("mmm") or 0,
                       earnings_date=em.get("earnings_date"), company=em.get("company") or row["company"])
        except Exception as e:
            row["em_error"] = str(e)
        closes = {}
        for f in fridays:
            try:
                q = call(client, "/api/quote", symbol=sym, date=f.isoformat())
                closes[f.isoformat()] = q["close"]
                if q.get("company") and row["company"] == sym:
                    row["company"] = q["company"]
            except Exception as e:
                row.setdefault("fcp_error", str(e))
        row["fridays"] = closes
        rows[sym] = row
        good = "em" in row and base.isoformat() in closes
        ok += good
        failed += not good
        print(f"  {sym:8s} {'OK ' if good else 'ERR'} em={row.get('em')} mmm={row.get('mmm')} "
              f"fcp={closes.get(base.isoformat())} {row.get('em_error') or row.get('fcp_error') or ''}")
        time.sleep(0.5)

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "updated_et":  now_et.strftime("%Y-%m-%d %H:%M"),
        "base_friday": base.isoformat(),
        "fridays":     [f.isoformat() for f in fridays],
        "tickers":     tickers,
        "rows":        rows,
    }, indent=1), encoding="utf-8")
    print(f"\n{ok} OK, {failed} with gaps -> {OUT}")
    # fail the run only if nothing came back at all (Yahoo blocked), so a few bad tickers never stop the update
    sys.exit(1 if ok == 0 else 0)


if __name__ == "__main__":
    main()
