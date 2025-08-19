from flask import Flask, render_template_string, request, send_file
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter
import io
import os
from datetime import datetime
import psycopg2

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

    // Validate "To Date" >= "From Date"
    document.addEventListener("input", () => {
        let from = document.getElementById("from_date").value;
        let to = document.getElementById("to_date").value;
        if (from && to && to < from) {
            document.getElementById("to_date").setCustomValidity("To Date cannot be earlier than From Date");
        } else {
            document.getElementById("to_date").setCustomValidity("");
        }
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
          <input type="date" id="from_date" name="from_date" class="w-full border border-gray-300 rounded-lg p-3 focus:ring-2 focus:ring-green-400" required>
        </div>
        <div>
          <label class="block text-gray-700 font-medium mb-1">To</label>
          <input type="date" id="to_date" name="to_date" class="w-full border border-gray-300 rounded-lg p-3 focus:ring-2 focus:ring-green-400" required>
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
    can = canvas.Canvas(packet, pagesize=(612, 792))  # Letter size

    # Handle Name & Address (split by newline)
    name_lines = str(data.get("name", "")).splitlines()
    can.setFont("Times-Bold", 12)

    if name_lines:
        can.drawString(73, 647, name_lines[0].strip())  # First line (Name)

    can.setFont("Times-Roman", 12)
    for i, line in enumerate(name_lines[1:], start=1):
        clean_line = line.strip()
        if clean_line:  # Skip blank/empty lines
            can.drawString(73, 647 - (i * 14), clean_line)

    # Format dates to dd-mm-yyyy
    date = format_date_ddmmyyyy(data.get("date", ""))
    from_date = format_date_ddmmyyyy(data.get("from_date", ""))
    to_date = format_date_ddmmyyyy(data.get("to_date", ""))

    can.setFont("Times-Roman", 11)
    can.drawString(467, 711, date)
    can.drawString(310, 542, from_date)
    can.drawString(385, 542, to_date)

    # Charges + Remarks
    y_start = 477
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

    can.setFont("Times-Roman", 11)
    for i, (charge, remark) in enumerate(charge_fields):
        y = y_start - (i * step)
        can.drawString(310, y, str(data.get(charge, "")))
        can.drawString(390, y, str(data.get(remark, "")))

    # Total
    can.setFont("Times-Bold", 12)
    can.drawString(295, 340, str(data.get("total", "")))

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

# ✅ Connect to Supabase PostgreSQL
def insert_into_db(data):
    try:
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO pdf_records
            (name, date, from_date, to_date, cf_charges, godown_rent, courier_charges,
             electric_bill, internet_charges, local_freight, labour_charges, hamali_charges, total)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data.get("name"),
            data.get("date"),
            data.get("from_date"),
            data.get("to_date"),
            data.get("cf_charges"),
            data.get("godown_rent"),
            data.get("courier_charges"),
            data.get("electric_bill"),
            data.get("internet_charges"),
            data.get("local_freight"),
            data.get("labour_charges"),
            data.get("hamali_charges"),
            data.get("total"),
        ))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("❌ Database insert failed:", e)

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

    # Calculate total
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

    # ✅ Insert into Supabase PostgreSQL
    insert_into_db(data)

    # Generate PDF
    pdf_bytes = fill_pdf("template.pdf", data)

    # Use user's name (first line only) in download filename
    user_name = str(data.get("name", "document")).split("\n")[0].strip().replace(" ", "_")
    filename = f"{user_name}.pdf"

    return send_file(pdf_bytes,
                     as_attachment=True,
                     download_name=filename,
                     mimetype="application/pdf")