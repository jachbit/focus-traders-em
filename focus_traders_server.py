#!/usr/bin/env python3
"""Focus Traders Weekly EM — Local API Server"""

from flask import Flask, jsonify, request, send_file
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd
import numpy as np
import io, os, json

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

app = Flask(__name__)

# ── CORS (allow the HTML file to call us from file:// or localhost) ──
@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

@app.route('/api/quote', methods=['OPTIONS'])
@app.route('/api/em',    methods=['OPTIONS'])
@app.route('/api/export-pdf', methods=['OPTIONS'])
def handle_options():
    return '', 204

# ── Serve HTML ────────────────────────────────────────────────────────
@app.route('/')
def index():
    path = os.path.join(os.path.dirname(__file__), 'focus-traders-em.html')
    return send_file(path)

# ── Health check ──────────────────────────────────────────────────────
@app.route('/api/ping')
def ping():
    return jsonify({'status': 'ok', 'server': 'Focus Traders EM'})

# ── API: Friday Closing Price + Company Name ──────────────────────────
@app.route('/api/quote')
def api_quote():
    symbol   = request.args.get('symbol', '').strip().upper()
    date_str = request.args.get('date', '').strip()

    if not symbol or not date_str:
        return jsonify({'error': 'symbol and date are required'}), 400

    try:
        friday = datetime.strptime(date_str, '%Y-%m-%d')
        target_date = friday.date()
        ticker = yf.Ticker(symbol)

        start = (friday - timedelta(days=7)).strftime('%Y-%m-%d')
        end   = (friday + timedelta(days=3)).strftime('%Y-%m-%d')
        hist  = ticker.history(start=start, end=end, auto_adjust=True)

        if hist.empty:
            return jsonify({'error': f'No price data for {symbol}'}), 404

        # Strip timezone safely — yfinance returns tz-aware index (America/New_York)
        if hasattr(hist.index, 'tz') and hist.index.tz is not None:
            hist.index = hist.index.tz_convert(None)
        else:
            hist.index = pd.to_datetime(hist.index)

        # Compare by date only to avoid hour-of-day mismatches
        hist_dates = hist.index.normalize()
        target_ts  = pd.Timestamp(target_date)

        # Prefer exact Friday match; otherwise take the nearest trading day
        exact = hist[hist_dates == target_ts]
        if not exact.empty:
            close = float(exact.iloc[-1]['Close'])
        else:
            diffs = (hist_dates - target_ts).abs()
            close = float(hist.iloc[diffs.argmin()]['Close'])

        # Company name — fast_info first, fall back to info
        company = symbol
        try:
            fi = ticker.fast_info
            company = getattr(fi, 'display_name', None) or symbol
        except Exception:
            pass
        if company == symbol:
            try:
                info    = ticker.info
                company = info.get('longName') or info.get('shortName') or symbol
            except Exception:
                pass

        return jsonify({'close': round(close, 3), 'company': company})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── API: Expected Move (ATM straddle, next Friday expiry) ─────────────
@app.route('/api/em')
def api_em():
    symbol   = request.args.get('symbol', '').strip().upper()
    date_str = request.args.get('date', '').strip()

    if not symbol or not date_str:
        return jsonify({'error': 'symbol and date are required'}), 400

    try:
        friday      = datetime.strptime(date_str, '%Y-%m-%d')
        next_friday = friday + timedelta(days=7)

        ticker      = yf.Ticker(symbol)
        expirations = ticker.options          # tuple of 'YYYY-MM-DD' strings

        if not expirations:
            return jsonify({'error': f'No options listed for {symbol}'}), 404

        # Closest expiry to next Friday
        best = min(expirations,
                   key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - next_friday).days))

        chain = ticker.option_chain(best)
        calls = chain.calls
        puts  = chain.puts

        if calls.empty or puts.empty:
            return jsonify({'error': 'Options chain is empty'}), 404

        # Current price
        try:
            current = float(ticker.fast_info.last_price)
        except Exception:
            current = float(calls['strike'].median())

        # ATM strike
        atm_strike = float(calls.iloc[
            (calls['strike'] - current).abs().values.argmin()
        ]['strike'])

        atm_call = calls[calls['strike'] == atm_strike]
        atm_put  = puts[puts['strike']   == atm_strike]

        # If put strike missing, use nearest
        if atm_put.empty:
            atm_put = puts.iloc[
                [(puts['strike'] - atm_strike).abs().values.argmin()]
            ]

        if atm_call.empty or atm_put.empty:
            return jsonify({'error': 'ATM options not found'}), 404

        c = atm_call.iloc[0]
        p = atm_put.iloc[0]

        call_price = float(c.get('lastPrice') or c.get('ask') or 0)
        put_price  = float(p.get('lastPrice') or p.get('ask')  or 0)

        if call_price == 0 and put_price == 0:
            return jsonify({'error': 'Zero option prices — market may be closed'}), 404

        em = round(call_price + put_price, 3)

        return jsonify({
            'em':            em,
            'expiry':        best,
            'atm_strike':    atm_strike,
            'call_price':    round(call_price, 3),
            'put_price':     round(put_price,  3),
            'current_price': round(current,    3),
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── API: Export PDF ────────────────────────────────────────────────────
@app.route('/api/export-pdf', methods=['POST'])
def api_export_pdf():
    body        = request.get_json(force=True) or {}
    rows        = body.get('rows', [])
    friday_date = body.get('fridayDate', datetime.now().strftime('%Y-%m-%d'))

    gold   = colors.HexColor('#B8860B')
    dark   = colors.HexColor('#1a1a2e')
    green  = colors.HexColor('#006400')
    orange = colors.HexColor('#CC5500')
    light  = colors.HexColor('#f5f5f0')
    mid    = colors.HexColor('#e8e8e0')

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter),
                            leftMargin=0.45*inch, rightMargin=0.45*inch,
                            topMargin=0.4*inch,  bottomMargin=0.4*inch)

    title_sty = ParagraphStyle('T', fontName='Helvetica-Bold', fontSize=17,
                                textColor=dark, alignment=TA_CENTER, spaceAfter=2)
    sub_sty   = ParagraphStyle('S', fontName='Helvetica', fontSize=9,
                                textColor=colors.HexColor('#555555'),
                                alignment=TA_CENTER, spaceAfter=10)
    foot_sty  = ParagraphStyle('F', fontName='Helvetica', fontSize=7,
                                textColor=colors.grey, alignment=TA_CENTER)

    elems = [
        Paragraph('FOCUS TRADERS  —  WEEKLY EXPECTED MOVE', title_sty),
        Paragraph(f'Friday Date: {friday_date}  ·  Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}',
                  sub_sty),
        Spacer(1, 0.1*inch),
    ]

    # Build rows
    hdr = ['#', 'Date Range', 'Ticker', 'Company Name', 'EM', 'FCP Close', 'Low', 'High']
    tdata  = [hdr]
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
            lbl = r.get('label','').upper()
            if not lbl:
                continue
            ri = len(tdata)
            tdata.append([f'  {lbl}', '', '', '', '', '', '', ''])
            styles += [
                ('SPAN',       (0,ri), (-1,ri)),
                ('BACKGROUND', (0,ri), (-1,ri), colors.HexColor('#2a2a40')),
                ('TEXTCOLOR',  (0,ri), (-1,ri), colors.HexColor('#FFD700')),
                ('FONTNAME',   (0,ri), (-1,ri), 'Helvetica-Bold'),
                ('FONTSIZE',   (0,ri), (-1,ri), 8),
                ('ALIGN',      (0,ri), (-1,ri), 'LEFT'),
                ('TOPPADDING', (0,ri), (-1,ri), 4),
                ('BOTTOMPADDING',(0,ri),(-1,ri),4),
            ]
        elif r.get('type') == 'ticker' and r.get('ticker'):
            row_n += 1
            ri = len(tdata)
            tdata.append([
                str(row_n),
                r.get('dateRange', ''),
                r.get('ticker', ''),
                r.get('company', ''),
                r.get('em', '—'),
                r.get('fcp', '—'),
                r.get('low', '—'),
                r.get('high', '—'),
            ])
            styles += [
                ('TEXTCOLOR', (2,ri), (2,ri),  dark),
                ('FONTNAME',  (2,ri), (2,ri),  'Helvetica-Bold'),
                ('TEXTCOLOR', (5,ri), (5,ri),  green),
                ('TEXTCOLOR', (6,ri), (6,ri),  colors.HexColor('#8B6914')),
                ('TEXTCOLOR', (7,ri), (7,ri),  orange),
            ]

    col_w = [0.32*inch, 1.25*inch, 0.8*inch, 2.45*inch,
             0.88*inch, 1.05*inch, 1.0*inch,  1.0*inch]

    t = Table(tdata, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle(styles))
    elems.append(t)
    elems.append(Spacer(1, 0.15*inch))
    elems.append(Paragraph(
        'Data sourced from Yahoo Finance via yfinance. Not financial advice.',
        foot_sty))

    doc.build(elems)
    buf.seek(0)

    fname = f'FocusTradersEM_{friday_date.replace("-","")}.pdf'
    return send_file(buf, as_attachment=True,
                     download_name=fname, mimetype='application/pdf')


if __name__ == '__main__':
    print()
    print('=' * 52)
    print('  FOCUS TRADERS WEEKLY EM  —  Local Server')
    print('=' * 52)
    print('  Dashboard: http://localhost:5000')
    print('  Press Ctrl+C to stop')
    print('=' * 52)
    print()
    app.run(debug=False, port=5000, host='0.0.0.0')
