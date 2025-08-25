import io
import os
from typing import Dict, Any
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from PyPDF2 import PdfReader, PdfWriter
from .helpers import to_number, format_date_ddmmyyyy

PAGE_W, PAGE_H = letter

def create_overlay_pdf(data: Dict[str, Any]) -> io.BytesIO:
    """Creates an in-memory PDF overlay with dynamic data."""
    buf = io.BytesIO()
    can = canvas.Canvas(buf, pagesize=(PAGE_W, PAGE_H))
    name_lines = str(data.get("name", "")).splitlines()
    can.setFont("Times-Bold", 12)
    if name_lines:
        can.drawString(73, 656, name_lines[0].strip())
    can.setFont("Times-Roman", 12)
    for i, line in enumerate(name_lines[1:], start=1):
        if line.strip():
            can.drawString(73, 656 - (i * 14), line.strip())
    date = format_date_ddmmyyyy(data.get("date", ""))
    from_date = format_date_ddmmyyyy(data.get("from_date", ""))
    to_date = format_date_ddmmyyyy(data.get("to_date", ""))
    can.setFont("Times-Roman", 11)
    can.drawString(467, 715, date)
    can.drawString(310, 547, from_date)
    can.drawString(385, 547, to_date)
    charges = data.get("charges") or []
    filtered_charges = [ch for ch in charges if str(ch.get("type", "")).strip() or str(ch.get("remark", "")).strip() or to_number(ch.get("amount", 0)) > 0]
    table_data = [["SR", "PARTICULAR", "AMOUNT", "REMARK"]]
    for i, ch in enumerate(filtered_charges, start=1):
        table_data.append([str(i), str(ch.get("type", "")), f"{to_number(ch.get('amount', 0)):.2f}", str(ch.get("remark", ""))])
    table_data.append(["", "TOTAL", f"{to_number(data.get('total', 0)):.2f}", ""])
    TABLE_LEFT, TABLE_TOP_Y = 60, 510
    TABLE_WIDTHS, ROW_HEIGHT = [40, 230, 90, 132], 18
    FONT_SIZE_BODY, FONT_SIZE_HEADER = 10, 11
    num_rows = len(table_data)
    tbl = Table(table_data, colWidths=TABLE_WIDTHS, rowHeights=[ROW_HEIGHT] * num_rows)
    tbl.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.8, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), FONT_SIZE_HEADER),
        ("BACKGROUND", (0, 0), (-1, 0), colors.white),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("FONTNAME", (0, 1), (-1, -1), "Times-Roman"),
        ("FONTSIZE", (0, 1), (-1, -1), FONT_SIZE_BODY),
        ("FONTNAME", (1, -1), (2, -1), "Times-Bold"),
        ("ALIGN", (1, -1), (1, -1), "RIGHT"),
        ("ALIGN", (2, 1), (2, -1), "RIGHT"),
        ("ALIGN", (2, -1), (2, -1), "RIGHT"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.white),
        ("TEXTCOLOR", (0, -1), (-1, -1), colors.black),
        ("SPAN", (0, -1), (0, -1)),
    ]))
    table_height = num_rows * ROW_HEIGHT
    table_bottom_y = TABLE_TOP_Y - table_height
    tbl.wrapOn(can, TABLE_LEFT, table_bottom_y)
    tbl.drawOn(can, TABLE_LEFT, table_bottom_y)
    note_text = """Please credit the expenses in our account
Account Name :- Sai Agro Inputs
Account No. :- 921020042670090
IFSC Code :- UTIB0000749
Bank :- Axis Bank
Branch :- Amankha Plot Road Akola"""
    can.setFont("Times-Roman", 12)
    text_x, text_y = TABLE_LEFT, table_bottom_y - 40
    for line in note_text.splitlines():
        can.drawString(text_x, text_y, line)
        text_y -= 14
    can.save()
    buf.seek(0)
    return buf

def fill_pdf_with_overlay(template_path: str, data: Dict[str, Any]) -> io.BytesIO:
    """Merges a template PDF with a generated overlay PDF."""
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template file '{template_path}' not found")
    with open(template_path, "rb") as f:
        base_pdf = PdfReader(f)
        overlay_pdf = PdfReader(create_overlay_pdf(data))
        writer = PdfWriter()
        page = base_pdf.pages[0]
        page.merge_page(overlay_pdf.pages[0])
        writer.add_page(page)
        output = io.BytesIO()
        writer.write(output)
        output.seek(0)
        return output