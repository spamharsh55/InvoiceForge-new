from flask import Flask, render_template_string, request, send_file
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter
import io
import os
from datetime import datetime

app = Flask(__name__)

# Tailwind-based HTML Form
HTML_FORM = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>PDF Generator</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    function updateTotal() {
        let fields = [
            "cf_charges", "godown_rent", "courier_charges", "electric_bill",
            "internet_charges", "local_freight", "labour_charges", "hamali_charges"
        ];
        let total = 0;
        fields.forEach(id => {
            let val = parseFloat(document.querySelector(`[name="${id}"]`).value) || 0;
            total += val;
        });
        document.querySelector('[name="total"]').value = total.toFixed(2);
    }

    // Auto-fill today's date
    document.addEventListener("DOMContentLoaded", () => {
        let today = new Date().toISOString().split("T")[0];
        document.getElementById("date").value = today;
    });
  </script>
</head>
<body class="bg-gray-100 min-h-screen flex items-center justify-center font-sans">
  <div class="w-full max-w-4xl bg-white rounded-2xl shadow-lg p-8">
    <h1 class="text-3xl font-bold text-center text-green-600 mb-6">📄 PDF Generator</h1>

    <form method="post" action="/generate" class="space-y-6">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <label class="block text-gray-700 font-medium mb-1">Name & Address</label>
          <textarea name="name" class="w-full border border-gray-300 rounded-lg p-3 focus:ring-2 focus:ring-green-400" rows="3" required></textarea>
        </div>
        <div>
          <label class="block text-gray-700 font-medium mb-1">Date</label>
          <input type="date" name="date" id="date" class="w-full border border-gray-300 rounded-lg p-3 focus:ring-2 focus:ring-green-400" required>
        </div>
        <div>
          <label class="block text-gray-700 font-medium mb-1">From</label>
          <input type="date" name="from_date" class="w-full border border-gray-300 rounded-lg p-3 focus:ring-2 focus:ring-green-400" required>
        </div>
        <div>
          <label class="block text-gray-700 font-medium mb-1">To</label>
          <input type="date" name="to_date" class="w-full border border-gray-300 rounded-lg p-3 focus:ring-2 focus:ring-green-400" required>
        </div>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full border border-gray-300 rounded-lg overflow-hidden">
          <thead class="bg-gray-100">
            <tr>
              <th class="px-4 py-2 border">Charge Type</th>
              <th class="px-4 py-2 border">Amount</th>
              <th class="px-4 py-2 border">Remarks</th>
            </tr>
          </thead>
          <tbody>
            {% for charge, remarks in charge_fields %}
            <tr class="hover:bg-gray-50">
              <td class="px-4 py-2 border text-gray-700">{{ charge.replace('_', ' ').title() }}</td>
              <td class="px-4 py-2 border">
                <input name="{{ charge }}" class="w-full border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-green-400" oninput="updateTotal()">
              </td>
              <td class="px-4 py-2 border">
                <input name="{{ remarks }}" class="w-full border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-green-400">
              </td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>

      <div>
        <label class="block text-gray-700 font-medium mb-1">Total</label>
        <input name="total" class="w-full border border-gray-300 rounded-lg p-3 bg-gray-100" readonly required>
      </div>

      <div class="text-center">
        <button type="submit" class="px-6 py-3 bg-green-600 text-white rounded-lg shadow hover:bg-green-700 transition">
          Generate PDF
        </button>
      </div>
    </form>
  </div>
</body>
</html>
"""

def format_date_ddmmyyyy(date_str):
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%d-%m-%Y")
    except Exception:
        return date_str or ""

def create_overlay(data):
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(612, 792))

    # Name & Address
    name_lines = str(data.get("name", "")).splitlines()
    can.setFont("Times-Bold", 12)
    if name_lines:
        can.drawString(80, 620, name_lines[0].strip())
    can.setFont("Times-Roman", 10)
    for i, line in enumerate(name_lines[1:], start=1):
        clean_line = line.strip()
        if clean_line:
            can.drawString(80, 620 - (i * 14), clean_line)

    # Dates
    date = format_date_ddmmyyyy(data.get("date", ""))
    from_date = format_date_ddmmyyyy(data.get("from_date", ""))
    to_date = format_date_ddmmyyyy(data.get("to_date", ""))

    can.setFont("Times-Roman", 10)
    can.drawString(464, 680, date)
    can.drawString(330, 530, from_date)
    can.drawString(410, 530, to_date)

    # Charges + remarks
    y_start = 465
    step = 17
    charge_fields = [
        ("cf_charges", "cf_remarks"),
        ("godown_rent", "godown_remarks"),
        ("courier_charges", "courier_remarks"),
        ("electric_bill", "electric_remarks"),
        ("internet_charges", "internet_remarks"),
        ("local_freight", "local_remarks"),
        ("labour_charges", "labour_remarks"),
        ("hamali_charges", "hamali_remarks"),
    ]
    can.setFont("Times-Roman", 10)
    for i, (charge, remark) in enumerate(charge_fields):
        y = y_start - (i * step)
        can.drawString(320, y, str(data.get(charge, "")))
        can.drawString(413, y, str(data.get(remark, "")))

    # Total
    can.setFont("Times-Bold", 12)
    can.drawString(320, 328, str(data.get("total", "")))

    can.save()
    packet.seek(0)
    return packet

def fill_pdf(template_path, data):
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template file '{template_path}' not found")
    with open(template_path, "rb") as f:
        template_pdf = PdfReader(f)
        overlay_pdf = PdfReader(create_overlay(data))
        writer = PdfWriter()
        page = template_pdf.pages[0]
        page.merge_page(overlay_pdf.pages[0])
        writer.add_page(page)
        output = io.BytesIO()
        writer.write(output)
        output.seek(0)
        return output

@app.route("/", methods=["GET"])
def form():
    charge_fields = [
        ("cf_charges", "cf_remarks"),
        ("godown_rent", "godown_remarks"),
        ("courier_charges", "courier_remarks"),
        ("electric_bill", "electric_remarks"),
        ("internet_charges", "internet_remarks"),
        ("local_freight", "local_remarks"),
        ("labour_charges", "labour_remarks"),
        ("hamali_charges", "hamali_remarks"),
    ]
    return render_template_string(HTML_FORM, charge_fields=charge_fields)

@app.route("/generate", methods=["POST"])
def generate():
    data = {key: request.form[key] for key in request.form}
    charge_fields = [
        "cf_charges", "godown_rent", "courier_charges", "electric_bill",
        "internet_charges", "local_freight", "labour_charges", "hamali_charges"
    ]
    total = 0
    for field in charge_fields:
        try:
            total += float(data.get(field, 0) or 0)
        except ValueError:
            pass
    data["total"] = str(round(total, 2))
    pdf_bytes = fill_pdf("template.pdf", data)
    user_name = str(data.get("name", "document")).split("\n")[0].strip().replace(" ", "_")
    filename = f"{user_name}.pdf"
    return send_file(pdf_bytes, as_attachment=True, download_name=filename, mimetype="application/pdf")