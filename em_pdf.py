"""
F.O.C.U.S.© Traders Weekly EM — template PDF (one function for both PDF buttons)
Built from _TEMPLATES/jachbit_pdf_base_template.py v4.0 | Jachbit 2026

  build_pdf(rows, friday_iso, data_note="") -> PDF bytes
    rows: [{"type": "section", "label": ...} | {"type": "ticker", "ticker", "dateRange", "company",
            "em", "mmm", "fcp", "low", "high", optional "math"}]   (same shape the page sends)
  Used by focus_traders_server.py /api/export-pdf (PC, on-screen rows) and em_build.py (hourly online PDF).

Template notes:

INK-SAVING FORMAT — RULES (read before every PDF project):
  - White page background always — no fills, no bands, no shading
  - NO colored line bands anywhere — no orange/navy rules as decorative bands
  - Page header: white background, navy bold title, thin navy bottom rule only
  - Page footer: white background, grey text, thin grey top rule — min 0.5 inch (36pt) from bottom edge
  - Section titles (locked 2026-08-04): LIGHT_GREY band, accent (NAVY default) bold text,
    accent left bar (LINEBEFORE 3.5pt) + accent underline (LINEBELOW 0.8pt), 0.4pt MID_GREY box —
    use section_bar(); NEVER a solid navy/orange/brand-colour BACKGROUND fill
  - Table headers: LIGHT_GREY background only, navy bold text — NO colored rule bands
  - Table data rows: alternate WHITE / ROW_ALT only — no colored fills
  - Body text: BLACK on white
  - Accent colors used ONLY for data text highlights, never for fills or bands

USAGE:
  Copy this file into your project and rename it (e.g. generate_mypdf.py).
  Replace the build() story content with your own.
  Run: python generate_mypdf.py

DEPENDENCIES: pip install reportlab
"""

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from datetime import datetime
import io
import os

# ── Brand Colors ─────────────────────────────────────────────────────────────
# Use these exactly — no new background fill colors
NAVY       = colors.Color(0.0,   0.168627, 0.360784)    # rgb(0, 43, 92)
ORANGE     = colors.Color(0.901961, 0.360784, 0.0)      # rgb(230, 92, 0)  — text only
DARK_GREY  = colors.Color(0.266667, 0.266667, 0.266667) # rgb(68, 68, 68)
BLACK      = colors.black
WHITE      = colors.white
LIGHT_GREY = colors.Color(0.94, 0.94, 0.94)   # table header bg only
MID_GREY   = colors.Color(0.82, 0.82, 0.82)   # rules and grid lines
ROW_ALT    = colors.Color(0.97, 0.97, 0.97)   # table row alt — very subtle
GREEN_DARK = colors.Color(0.05, 0.38, 0.15)
RED_DARK   = colors.Color(0.55, 0.10, 0.02)
BLUE_MID   = colors.Color(0.10, 0.35, 0.65)

# ── Page Geometry ─────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = landscape(letter)
MARGIN_L = MARGIN_R = 48.0
MARGIN_T = 52.0
MARGIN_B = 72.0    # 1 inch bottom margin — keeps footer well within safe zone
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R   # ~516 pt usable width

# ── Style Factory ─────────────────────────────────────────────────────────────
def S(name, **kw):
    d = dict(fontName="Helvetica", fontSize=9, leading=13,
             textColor=BLACK, spaceAfter=0, spaceBefore=0)
    d.update(kw)
    return ParagraphStyle(name, **d)

# Title block
CTIT_S  = S("ct",  fontName="Helvetica-Bold", fontSize=20, textColor=NAVY,      leading=26, alignment=TA_CENTER)
CSUB_S  = S("cs",  fontSize=10, textColor=NAVY,  leading=14, alignment=TA_CENTER)
CDATE_S = S("cd",  fontSize=8,  textColor=DARK_GREY, leading=12, alignment=TA_CENTER)
DISC_S  = S("ds",  fontName="Helvetica-Oblique", fontSize=7, textColor=DARK_GREY, leading=10, alignment=TA_CENTER)

# Section headers — text style for section_bar() (LIGHT_GREY band + accent left bar/underline, no fill)
SEC_S   = S("sc",  fontName="Helvetica-Bold", fontSize=10, textColor=NAVY, leading=14)

# Body text
BODY_S  = S("bd",  fontSize=8.5, textColor=BLACK,     leading=12.5)
BOLD_S  = S("bo",  fontName="Helvetica-Bold", fontSize=8.5, textColor=BLACK, leading=12.5)
NAVY_S  = S("nv",  fontName="Helvetica-Bold", fontSize=8.5, textColor=NAVY,  leading=12.5)
SMALL_S = S("sm",  fontSize=7.5, textColor=BLACK,     leading=11)
LINK_S  = S("lk",  fontSize=8,   textColor=BLUE_MID,  leading=11)
WARN_S  = S("wn",  fontSize=8.5, textColor=RED_DARK,  leading=12.5)
BUL_S   = S("bl",  fontSize=8.5, textColor=BLACK,     leading=13, leftIndent=10)

# Footer styles
FOOT_S  = S("ft",  fontSize=6.5, textColor=DARK_GREY, leading=9,  alignment=TA_CENTER)
VERSE_S = S("vs",  fontSize=6,   textColor=ORANGE,    leading=9,  alignment=TA_CENTER)
COPY_S  = S("cp",  fontSize=5.5, textColor=DARK_GREY, leading=8,  alignment=TA_CENTER)

# Table styles — header uses LIGHT_GREY fill only, never navy/colored fill
TH_S    = S("th",  fontName="Helvetica-Bold", fontSize=7.5, textColor=NAVY,  leading=10, alignment=TA_CENTER)
TD_S    = S("td",  fontSize=7.5, textColor=BLACK, leading=11, alignment=TA_CENTER)
TD_L    = S("tdl", fontSize=7.5, textColor=BLACK, leading=11, alignment=TA_LEFT)
TD_B    = S("tdb", fontName="Helvetica-Bold", fontSize=7.5, textColor=NAVY,  leading=11, alignment=TA_LEFT)

# ── Page Header / Footer ──────────────────────────────────────────────────────
NOW_STR  = datetime.now().strftime("%Y-%m-%d %H:%M")
DATE_STR = datetime.now().strftime("%Y-%m-%d")

PROJECT_TITLE = "F.O.C.U.S.© — Traders Weekly EM"
FOOTER_LABEL  = "Traders Weekly EM"

def on_page(canvas, doc):
    canvas.saveState()

    # ── PAGE HEADER ──────────────────────────────────────────────────────────
    # White background, navy text, single thin navy rule at bottom — NO colored bands
    canvas.setFillColor(NAVY)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(MARGIN_L, PAGE_H - 20, PROJECT_TITLE)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(DARK_GREY)
    canvas.drawRightString(PAGE_W - MARGIN_R, PAGE_H - 20, f"Jachbit 2026  |  {DATE_STR}")
    canvas.setStrokeColor(MID_GREY)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN_L, PAGE_H - 24, PAGE_W - MARGIN_R, PAGE_H - 24)

    # ── PAGE FOOTER ──────────────────────────────────────────────────────────
    # Content starts at 54pt (~0.75 inch) from bottom — well within safe print margin
    # Thin grey rule only — NO orange/colored bands
    canvas.setStrokeColor(MID_GREY)
    canvas.setLineWidth(0.4)
    canvas.line(MARGIN_L, 54, PAGE_W - MARGIN_R, 54)

    # Line 1: document label (center) + page number (right)
    canvas.setFillColor(DARK_GREY)
    canvas.setFont("Helvetica", 6.5)
    canvas.drawCentredString(PAGE_W / 2, 44, f"F.O.C.U.S.©  |  Jachbit 2026  |  {FOOTER_LABEL}")
    canvas.setFillColor(NAVY)
    canvas.setFont("Helvetica-Bold", 6.5)
    canvas.drawRightString(PAGE_W - MARGIN_R, 44, f"Page {doc.page}")

    # Line 2: Bible verses — black bold, centered
    canvas.setFillColor(BLACK)
    canvas.setFont("Helvetica-Bold", 6)
    canvas.drawCentredString(PAGE_W / 2, 33,
        "John 3:16   |   1 John 3:16   |   Matt 6:33   |   Jer 33:3   |   Prov 3:5-6   |   Prov 27:17")

    # Line 3: copyright
    canvas.setFillColor(DARK_GREY)
    canvas.setFont("Helvetica", 5.5)
    canvas.drawCentredString(PAGE_W / 2, 22,
        "© 2026 Jachbit. All rights reserved. May not be copied or shared without express written consent of the publisher.  linktr.ee/jachbit")

    canvas.restoreState()

# ── Reusable Helpers ──────────────────────────────────────────────────────────
def sp(n=6):
    """Vertical spacer."""
    return Spacer(1, n)

def section_bar(text, accent=NAVY):
    """
    Section header (rule locked 2026-08-04) — 1-cell Table: LIGHT_GREY band,
    accent bold text, accent LEFT BAR (3.5pt) + accent UNDERLINE (0.8pt), 0.4pt MID_GREY box.
    NEVER a solid accent fill. NAVY is the default accent.
    """
    t = Table([[Paragraph(text, ParagraphStyle("sc_acc", parent=SEC_S, textColor=accent))]],
              colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), LIGHT_GREY),
        ("LINEBEFORE",    (0,0), (0,0),   3.5, accent),
        ("LINEBELOW",     (0,0), (-1,-1), 0.8, accent),
        ("BOX",           (0,0), (-1,-1), 0.4, MID_GREY),
        ("TOPPADDING",    (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("LEFTPADDING",   (0,0), (-1,-1), 7),
    ]))
    return t

def grey_rule():
    """Thin grey divider rule — use between sections."""
    return HRFlowable(width=CONTENT_W, thickness=0.5, color=MID_GREY, spaceAfter=6, spaceBefore=4)

def std_table_style(has_header=True):
    """
    Standard table style: LIGHT_GREY header row (navy text), alternating white/ROW_ALT,
    grey grid lines. No orange bands anywhere.
    """
    base = [
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 5),
        ("RIGHTPADDING",  (0,0), (-1,-1), 5),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE, ROW_ALT]),
        ("LINEBELOW",     (0,0), (-1,-2), 0.3, MID_GREY),
        ("BOX",           (0,0), (-1,-1), 0.5, MID_GREY),
        ("GRID",          (0,0), (-1,-1), 0.3, MID_GREY),
    ]
    if has_header:
        base += [
            ("BACKGROUND",  (0,0), (-1,0), LIGHT_GREY),
            ("LINEBELOW",   (0,0), (-1,0), 0.5, MID_GREY),  # grey only — no orange
        ]
    return TableStyle(base)

def info_table_style():
    """
    Two-column info table (label | value). No header row. White/ROW_ALT alternating.
    """
    return TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("RIGHTPADDING",  (0,0), (-1,-1), 6),
        ("ROWBACKGROUNDS",(0,0), (-1,-1), [WHITE, ROW_ALT]),
        ("LINEBELOW",     (0,0), (-1,-2), 0.4, MID_GREY),
        ("BOX",           (0,0), (-1,-1), 0.5, MID_GREY),
    ])

# ── Build Function ────────────────────────────────────────────────────────────
COLS   = ["#", "DATE RANGE", "TICKER", "COMPANY", "EM", "+MMM", "FRIDAY CLOSE", "EM LOW", "EM HIGH", "MATH (FCP -/+ (EM + MMM))"]
COL_WF = [0.03, 0.10, 0.065, 0.17, 0.06, 0.055, 0.08, 0.07, 0.07, 0.30]
TD_R   = ParagraphStyle("tdr", parent=TD_S, alignment=TA_RIGHT)
MATH_S = ParagraphStyle("mth", parent=TD_L, fontSize=6.8, leading=9, textColor=DARK_GREY)


def _num(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _math(r):
    """Show the math (rule 16): FCP -/+ (EM + MMM) with the live values."""
    if r.get("math"):
        return r["math"]
    fcp, em, mmm = _num(r.get("fcp")), _num(r.get("em")), _num(r.get("mmm")) or 0.0
    if fcp is None or em is None:
        return "EM or Friday close missing" + (" (futures: type the EM by hand)" if "=F" in str(r.get("ticker", "")) else "")
    tot = em + mmm
    return (f"{fcp:,.3f} - ({em:,.3f} + {mmm:,.3f}) = {fcp - tot:,.3f}  |  "
            f"{fcp:,.3f} + {tot:,.3f} = {fcp + tot:,.3f}")


def _table(items):
    head = [Paragraph(h, TH_S) for h in COLS]
    data = [head]
    for n, r in items:
        data.append([
            Paragraph(str(n), TD_S), Paragraph(escape_(r.get("dateRange", "")), TD_S),
            Paragraph(f"<b>{escape_(r.get('ticker', ''))}</b>", TD_B), Paragraph(escape_(r.get("company", "")), TD_L),
            Paragraph(escape_(r.get("em", "")), TD_R), Paragraph(escape_(r.get("mmm", "")), TD_R),
            Paragraph(escape_(r.get("fcp", "")), TD_R),
            Paragraph(f"<font color='#8c1a05'>{escape_(r.get('low', ''))}</font>", TD_R),
            Paragraph(f"<font color='#0d6126'>{escape_(r.get('high', ''))}</font>", TD_R),
            Paragraph(escape_(_math(r)), MATH_S),
        ])
    t = Table(data, colWidths=[CONTENT_W * w for w in COL_WF], repeatRows=1)
    t.setStyle(std_table_style())
    t.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t


def escape_(v):
    return str(v if v is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_pdf(rows, friday_iso="", data_note=""):
    global NOW_STR, DATE_STR
    NOW_STR  = datetime.now().strftime("%Y-%m-%d %H:%M")
    DATE_STR = datetime.now().strftime("%Y-%m-%d")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter),
                            leftMargin=MARGIN_L, rightMargin=MARGIN_R, topMargin=MARGIN_T, bottomMargin=MARGIN_B,
                            title="F.O.C.U.S.© — Traders Weekly EM", author="Jachbit 2026")

    tickers = [r for r in rows if r.get("type") == "ticker" and str(r.get("ticker", "")).strip()]
    story = [sp(2), Paragraph("F.O.C.U.S.©", CSUB_S), sp(2), Paragraph("Traders Weekly EM", CTIT_S), sp(4),
             Paragraph("Weekly expected move: Friday close, EM, +MMM on earnings weeks, EM low / high", CDATE_S), sp(3)]
    sub = [f"Jachbit 2026", NOW_STR, f"{len(tickers)} rows", f"Friday {friday_iso or '—'}"]
    if data_note:
        sub.append(data_note)
    sub.append(", ".join(str(r["ticker"]).strip() for r in tickers))
    story += [Paragraph("  ·  ".join(escape_(x) for x in sub), DISC_S), sp(3),
              Paragraph("EM = Spot x ATM IV x &radic;(DTE / 365), expiry nearest next Friday  ·  "
                        "+MMM = ATM straddle of the expiry nearest earnings, when earnings fall in the week  ·  "
                        "EM Low / High = Friday close -/+ (EM + MMM)", CDATE_S),
              sp(4), grey_rule()]

    # group rows under their section bars (a blank section label continues the list without a bar)
    groups, label, items, n = [], "", [], 0
    for r in rows:
        if r.get("type") == "section":
            if items:
                groups.append((label, items))
            label, items = str(r.get("label", "")).strip(), []
        elif r.get("type") == "ticker" and str(r.get("ticker", "")).strip():
            n += 1
            items.append((n, r))
    if items:
        groups.append((label, items))

    for label, items in groups:
        block = []
        if label:
            block += [section_bar(f"{escape_(label.upper())}  ({len(items)})"), sp(4)]
        block.append(_table(items))
        story += [KeepTogether(block) if len(items) <= 12 else block[-1], sp(8)]

    story += [Paragraph("For personal research only, not financial advice. Data: Yahoo Finance (yFinance).", DISC_S)]
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()


if __name__ == "__main__":
    demo = [{"type": "ticker", "ticker": "SPY", "dateRange": "20261113-1120", "company": "SPDR S&P 500 ETF",
             "em": "16.957", "mmm": "—", "fcp": "754.370", "low": "737.413", "high": "771.327"}]
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       f"FOCUS_Traders_EM_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
    open(out, "wb").write(build_pdf(demo, "2026-11-13", "demo"))
    print("PDF generated:", out)
