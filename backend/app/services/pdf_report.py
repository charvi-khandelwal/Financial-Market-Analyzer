from __future__ import annotations
from io import BytesIO
from typing import Dict, Any

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

def render_pdf(report: Dict[str, Any]) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    w, h = letter

    x = 50
    y = h - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(x, y, "Market & Sentiment Report")
    y -= 24

    c.setFont("Helvetica", 10)
    c.drawString(x, y, f"Generated at: {report.get('generated_at','')}")
    y -= 18
    c.drawString(x, y, f"Sentiment mood: {report.get('sentiment_mood','')}")
    y -= 14
    c.drawString(x, y, f"Sentiment score: {report.get('sentiment_score','')}")
    y -= 22

    c.setFont("Helvetica-Bold", 12)
    c.drawString(x, y, "Snapshot")
    y -= 16
    c.setFont("Helvetica", 10)

    snap = report.get("market_snapshot", {}) or {}
    for k, v in snap.items():
        line = f"- {k}: {v}"
        if y < 80:
            c.showPage()
            y = h - 50
            c.setFont("Helvetica", 10)
        c.drawString(x, y, line[:120])
        y -= 14

    y -= 10
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x, y, "Notes")
    y -= 16
    c.setFont("Helvetica", 10)
    for n in report.get("notes", []):
        if y < 80:
            c.showPage()
            y = h - 50
            c.setFont("Helvetica", 10)
        c.drawString(x, y, f"• {n}"[:120])
        y -= 14

    c.showPage()
    c.save()
    return buf.getvalue()
