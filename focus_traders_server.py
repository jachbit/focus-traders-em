#!/usr/bin/env python3
"""
Focus Traders Weekly EM — Local API Server

EM calculation:
  EM  = Spot × ATM_IV × √(DTE / 365)   ← matches TOS IV banner
  MMM = ATM straddle of expiry nearest earnings (auto-detected, 0 if no earnings)
  Total EM shown on dashboard = EM + MMM

Data sources:
  /api/em    — yfinance implied volatility (IV-based, matches TOS)
  /api/quote — yfinance historical Friday closing price
  MMM        — yfinance earnings calendar (automatic)
"""

import os, io, pathlib
from datetime import datetime, timedelta

from flask import Flask, jsonify, request, send_file
import yfinance as yf
import pandas as pd

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_LEFT

HERE = pathlib.Path(__file__).resolve().parent

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__)

@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin']  = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

@app.route('/api/quote',      methods=['OPTIONS'])
@app.route('/api/em',         methods=['OPTIONS'])
@app.route('/api/export-pdf', methods=['OPTIONS'])
def handle_options():
    return '', 204

@app.route('/')
def index():
    return send_file(os.path.join(os.path.dirname(__file__), 'focus-traders-em.html'))

@app.route('/api/ping')
def ping():
    return jsonify({'status': 'ok', 'server': 'Focus Traders EM'})


# ── Static display names (reliable fallback for common tickers) ───────────────
_DISPLAY_NAMES = {
    "^SPX": "S&P 500 Index", "SPY": "SPDR S&P 500 ETF",
    "^NDX": "Nasdaq 100 Index", "QQQ": "Invesco QQQ Trust",
    "^DJI": "Dow Jones Industrial Avg", "DIA": "SPDR Dow Jones ETF",
    "^RUT": "Russell 2000 Index", "IWM": "iShares Russell 2000 ETF",
    "^VIX": "CBOE Volatility Index",
    "ES=F": "E-Mini S&P 500 Futures", "NQ=F": "E-Mini Nasdaq 100 Futures",
    "YM=F": "E-Mini Dow Jones Futures", "RTY=F": "E-Mini Russell 2000 Futures",
    "GLD": "SPDR Gold Shares", "SLV": "iShares Silver Trust",
    "TLT": "iShares 20+ Yr Treasury ETF", "HYG": "iShares High Yield Corp Bond ETF",
    "XLK": "Technology Select Sector SPDR", "XLF": "Financial Select Sector SPDR",
    "XLE": "Energy Select Sector SPDR", "XLV": "Health Care Select Sector SPDR",
    "XLI": "Industrial Select Sector SPDR", "XLY": "Consumer Discretionary SPDR",
    "ARKK": "ARK Innovation ETF", "ARKW": "ARK Next Gen Internet ETF",
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def _composite_iv(call_iv, put_iv):
    """Average two IV values; use whichever is available if one is missing."""
    c = max(float(call_iv or 0), 0.0)
    p = max(float(put_iv  or 0), 0.0)
    if c > 0 and p > 0:
        return (c + p) / 2
    return c or p

def _iv_em(spot, composite_iv, dte):
    """EM = Spot × IV × √(DTE/365). Returns 0 if inputs invalid."""
    if spot <= 0 or composite_iv <= 0 or dte <= 0:
        return 0.0
    return round(spot * composite_iv * (dte / 365) ** 0.5, 3)


# ── Symbols with no earnings (indices, ETFs, futures) ─────────────────────────
NO_EARNINGS_SYMBOLS = {
    '^SPX', '^GSPC', '^NDX', '^RUT', '^VIX', '^DJI',
    'SPY', 'QQQ', 'DIA', 'IWM', 'GLD', 'SLV', 'TLT', 'VXX',
    'ES=F', 'NQ=F', 'YM=F', 'RTY=F', 'GC=F', 'CL=F',
}


# ── Auto-detect earnings MMM ──────────────────────────────────────────────────
def _get_earnings_mmm(symbol, from_date, to_date):
    """
    Check if earnings fall within [from_date, to_date].
    If yes → ATM straddle of nearest expiry to earnings = MMM.
    Returns (mmm_float, earnings_date_str) or (0.0, None).
    """
    if symbol in NO_EARNINGS_SYMBOLS:
        return 0.0, None

    try:
        ticker = yf.Ticker(symbol)
        cal    = ticker.calendar
        if cal is None:
            return 0.0, None

        earnings_dt = None
        try:
            if isinstance(cal, dict):
                earn_list = cal.get('Earnings Date', [])
                if earn_list:
                    earnings_dt = pd.Timestamp(earn_list[0]).date()
            else:
                if 'Earnings Date' in cal.index:
                    val = cal.loc['Earnings Date'].iloc[0]
                    earnings_dt = pd.Timestamp(val).date()
        except Exception:
            return 0.0, None

        if earnings_dt is None:
            return 0.0, None

        from_d = from_date.date() if hasattr(from_date, 'date') else from_date
        to_d   = to_date.date()   if hasattr(to_date,   'date') else to_date

        if not (from_d <= earnings_dt <= to_d):
            return 0.0, None

        # Find expiry nearest to earnings
        expirations = ticker.options
        if not expirations:
            return 0.0, None

        earn_dt_obj = datetime.combine(earnings_dt, datetime.min.time())
        nearest_exp = min(
            expirations,
            key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - earn_dt_obj).days)
        )

        chain = ticker.option_chain(nearest_exp)
        calls, puts = chain.calls, chain.puts
        if calls.empty or puts.empty:
            return 0.0, None

        try:
            spot = float(ticker.fast_info.last_price)
        except Exception:
            spot = float(calls['strike'].median())

        atm_strike = float(
            calls.iloc[(calls['strike'] - spot).abs().values.argmin()]['strike']
        )
        atm_call = calls[calls['strike'] == atm_strike]
        atm_put  = puts[puts['strike']   == atm_strike]
        if atm_put.empty:
            atm_put = puts.iloc[[(puts['strike'] - atm_strike).abs().values.argmin()]]
        if atm_call.empty or atm_put.empty:
            return 0.0, None

        c, p = atm_call.iloc[0], atm_put.iloc[0]

        def _mid(row):
            bid = float(row.get('bid', 0) or 0)
            ask = float(row.get('ask', 0) or 0)
            if bid > 0 and ask > 0:
                return (bid + ask) / 2
            return float(row.get('lastPrice', 0) or 0)

        mmm = round(_mid(c) + _mid(p), 3)
        if mmm <= 0:
            return 0.0, None

        earn_str = earnings_dt.strftime('%Y-%m-%d')
        print(f"  {symbol}: MMM={mmm}  earnings={earn_str}  exp={nearest_exp}  [auto]")
        return mmm, earn_str

    except Exception as e:
        print(f"  {symbol}: MMM check failed ({e})")
        return 0.0, None


# ── API: Friday Closing Price ─────────────────────────────────────────────────
@app.route('/api/quote')
def api_quote():
    symbol   = request.args.get('symbol', '').strip().upper()
    date_str = request.args.get('date',   '').strip()

    if not symbol or not date_str:
        return jsonify({'error': 'symbol and date are required'}), 400

    try:
        friday      = datetime.strptime(date_str, '%Y-%m-%d')
        target_date = friday.date()
        ticker      = yf.Ticker(symbol)

        start = (friday - timedelta(days=7)).strftime('%Y-%m-%d')
        end   = (friday + timedelta(days=3)).strftime('%Y-%m-%d')
        hist  = ticker.history(start=start, end=end, auto_adjust=True)

        if hist.empty:
            return jsonify({'error': f'No price data for {symbol}'}), 404

        if hasattr(hist.index, 'tz') and hist.index.tz is not None:
            hist.index = hist.index.tz_convert(None)
        else:
            hist.index = pd.to_datetime(hist.index)

        hist_dates = hist.index.normalize()
        target_ts  = pd.Timestamp(target_date)
        exact      = hist[hist_dates == target_ts]
        close      = float(exact.iloc[-1]['Close']) if not exact.empty else \
                     float(hist.iloc[(hist_dates - target_ts).abs().argmin()]['Close'])

        company = _DISPLAY_NAMES.get(symbol)
        if not company:
            try:
                info    = ticker.info
                company = info.get('longName') or info.get('shortName') or ''
            except Exception:
                pass
        if not company:
            company = symbol

        return jsonify({'close': round(close, 3), 'company': company})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── API: Expected Move (IV-based) + Auto MMM ──────────────────────────────────
@app.route('/api/em')
def api_em():
    symbol   = request.args.get('symbol', '').strip().upper()
    date_str = request.args.get('date',   '').strip()

    if not symbol or not date_str:
        return jsonify({'error': 'symbol and date are required'}), 400

    try:
        friday      = datetime.strptime(date_str, '%Y-%m-%d')
        next_friday = friday + timedelta(days=7)

        ticker      = yf.Ticker(symbol)
        expirations = ticker.options

        if not expirations:
            return jsonify({'error': f'No options listed for {symbol}'}), 404

        # Expiry closest to next Friday
        best = min(expirations,
                   key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - next_friday).days))

        chain = ticker.option_chain(best)
        calls, puts = chain.calls, chain.puts

        if calls.empty or puts.empty:
            return jsonify({'error': 'Options chain is empty'}), 404

        try:
            spot = float(ticker.fast_info.last_price)
        except Exception:
            spot = float(calls['strike'].median())

        # ATM strike
        atm_strike = float(
            calls.iloc[(calls['strike'] - spot).abs().values.argmin()]['strike']
        )
        atm_call = calls[calls['strike'] == atm_strike]
        atm_put  = puts[puts['strike']   == atm_strike]

        if atm_put.empty:
            atm_put = puts.iloc[[(puts['strike'] - atm_strike).abs().values.argmin()]]
        if atm_call.empty or atm_put.empty:
            return jsonify({'error': 'ATM options not found'}), 404

        c, p = atm_call.iloc[0], atm_put.iloc[0]

        # yfinance impliedVolatility is already decimal (e.g. 0.3626)
        call_iv = float(c.get('impliedVolatility', 0) or 0)
        put_iv  = float(p.get('impliedVolatility', 0) or 0)
        comp_iv = _composite_iv(call_iv, put_iv)

        if comp_iv <= 0:
            return jsonify({'error': 'No IV data — market may be closed'}), 404

        expiry_dt = datetime.strptime(best, '%Y-%m-%d')
        dte       = max((expiry_dt.date() - datetime.now().date()).days, 1)
        em        = _iv_em(spot, comp_iv, dte)

        if em <= 0:
            return jsonify({'error': 'Could not compute EM'}), 404

        print(f"  {symbol}: EM={em}  IV={comp_iv:.4f}  DTE={dte}  strike={atm_strike}  [yfinance]")

        # Auto-detect MMM from earnings calendar
        mmm, earnings_date = _get_earnings_mmm(symbol, friday, next_friday)

        company = _DISPLAY_NAMES.get(symbol)
        if not company:
            try:
                info    = ticker.info
                company = info.get('longName') or info.get('shortName') or symbol
            except Exception:
                company = symbol

        return jsonify({
            'em':            em,
            'expiry':        best,
            'atm_strike':    atm_strike,
            'iv':            round(comp_iv, 4),
            'current_price': round(spot, 3),
            'source':        'yfinance',
            'mmm':           mmm,
            'earnings_date': earnings_date,
            'company':       company,
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── API: Export PDF ───────────────────────────────────────────────────────────
@app.route('/api/export-pdf', methods=['POST'])
def api_export_pdf():
    body        = request.get_json(force=True) or {}
    rows        = body.get('rows', [])
    friday_date = body.get('fridayDate', datetime.now().strftime('%Y-%m-%d'))

    gold   = colors.HexColor('#B8860B')
    dark   = colors.HexColor('#1a1a2e')
    green  = colors.HexColor('#006400')
    orange = colors.HexColor('#CC5500')
    purple = colors.HexColor('#7B2D8B')
    light  = colors.HexColor('#f5f5f0')
    mid    = colors.HexColor('#e8e8e0')

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter),
                            leftMargin=0.4*inch, rightMargin=0.4*inch,
                            topMargin=0.4*inch,  bottomMargin=0.4*inch)

    title_sty = ParagraphStyle('T', fontName='Helvetica-Bold', fontSize=17,
                                textColor=dark, alignment=TA_CENTER, spaceAfter=8)
    sub_sty   = ParagraphStyle('S', fontName='Helvetica', fontSize=9,
                                textColor=colors.HexColor('#555555'),
                                alignment=TA_CENTER, spaceAfter=10)
    foot_sty  = ParagraphStyle('F', fontName='Helvetica', fontSize=7,
                                textColor=colors.grey, alignment=TA_CENTER)

    elems = [
        Paragraph('FOCUS TRADERS  —  WEEKLY EXPECTED MOVE', title_sty),
        Paragraph(
            f'Friday Date: {friday_date}  ·  Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}',
            sub_sty),
        Spacer(1, 0.1*inch),
    ]

    hdr   = ['#', 'Date Range', 'Ticker', 'Company Name', 'EM', '+MMM', 'Friday Close Price', 'EM Low', 'EM High']
    tdata = [hdr]
    styles = [
        ('BACKGROUND',    (0,0), (-1,0),  dark),
        ('TEXTCOLOR',     (0,0), (-1,0),  colors.white),
        ('FONTNAME',      (0,0), (-1,0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0,0), (-1,0),  9),
        ('ALIGN',         (0,0), (-1,0),  'CENTER'),
        ('TOPPADDING',    (0,0), (-1,0),  7),
        ('BOTTOMPADDING', (0,0), (-1,0),  7),
        ('LINEBELOW',     (0,0), (-1,0),  2,   gold),
        ('FONTNAME',      (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE',      (0,1), (-1,-1), 8),
        ('ALIGN',         (0,1), (-1,-1), 'CENTER'),
        ('ALIGN',         (3,1), (3,-1),  'LEFT'),
        ('TOPPADDING',    (0,1), (-1,-1), 5),
        ('BOTTOMPADDING', (0,1), (-1,-1), 5),
        ('LINEBELOW',     (0,1), (-1,-1), 0.4, colors.HexColor('#cccccc')),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [light, mid]),
    ]

    row_n = 0
    for r in rows:
        if r.get('type') == 'section':
            lbl = r.get('label', '').upper()
            if not lbl:
                continue
            ri = len(tdata)
            tdata.append([f'  {lbl}', '', '', '', '', '', '', '', ''])
            styles += [
                ('SPAN',          (0,ri), (-1,ri)),
                ('BACKGROUND',    (0,ri), (-1,ri), colors.HexColor('#2a2a40')),
                ('TEXTCOLOR',     (0,ri), (-1,ri), colors.HexColor('#FFD700')),
                ('FONTNAME',      (0,ri), (-1,ri), 'Helvetica-Bold'),
                ('FONTSIZE',      (0,ri), (-1,ri), 8),
                ('ALIGN',         (0,ri), (-1,ri), 'LEFT'),
                ('TOPPADDING',    (0,ri), (-1,ri), 4),
                ('BOTTOMPADDING', (0,ri), (-1,ri), 4),
            ]
        elif r.get('type') == 'ticker' and r.get('ticker'):
            row_n += 1
            ri = len(tdata)
            tdata.append([
                str(row_n),
                r.get('dateRange', ''),
                r.get('ticker',    ''),
                r.get('company',   ''),
                r.get('em',   '—'),
                r.get('mmm',  '—'),
                r.get('fcp',  '—'),
                r.get('low',  '—'),
                r.get('high', '—'),
            ])
            styles += [
                ('TEXTCOLOR', (2,ri), (2,ri), dark),
                ('FONTNAME',  (2,ri), (2,ri), 'Helvetica-Bold'),
                ('TEXTCOLOR', (5,ri), (5,ri), purple),
                ('TEXTCOLOR', (6,ri), (6,ri), green),
                ('TEXTCOLOR', (7,ri), (7,ri), colors.HexColor('#8B6914')),
                ('TEXTCOLOR', (8,ri), (8,ri), orange),
            ]

    col_w = [0.30*inch, 1.10*inch, 0.75*inch, 2.10*inch,
             0.80*inch, 0.75*inch, 1.0*inch, 0.90*inch, 0.90*inch]

    t = Table(tdata, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle(styles))
    elems.append(t)
    elems.append(Spacer(1, 0.15*inch))
    elems.append(Paragraph(
        'EM: Yahoo Finance implied volatility (IV-based, matches TOS) · '
        'MMM: auto-detected from earnings calendar · '
        'FCP: Yahoo Finance historical close · Not financial advice.',
        foot_sty))

    doc.build(elems)
    buf.seek(0)
    fname = f'FocusTradersEM_{friday_date.replace("-","")}.pdf'
    return send_file(buf, as_attachment=True, download_name=fname, mimetype='application/pdf')


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print()
    print('=' * 52)
    print('  FOCUS TRADERS WEEKLY EM  —  Local Server')
    print('=' * 52)
    print('  Dashboard : http://localhost:5000')
    print('  EM method : IV-based  (Spot × IV × √DTE/365)')
    print('  MMM       : Auto-detected from earnings calendar')
    print('  Press Ctrl+C to stop')
    print('=' * 52)
    print()
    app.run(debug=False, port=5000, host='0.0.0.0')
