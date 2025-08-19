from flask import Flask, render_template_string, request, send_file
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter
import io
import os
from datetime import datetime
from supabase import create_client, Client

# Flask app
app = Flask(__name__)

# Supabase client
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Tailwind Form UI
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

    document.addEventListener("DOMContentLoaded", () => {
        let today = new Date().toISOString().split("T")[0];
        document.getElementById("date").value = today;
    });

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
    can = canvas.Canvas(packet, pagesize=(612, 792))
    name_lines = str(data.get("name", "")).splitlines()
    can.setFont("Times-Bold", 12)
    if name_lines:
        can.drawString(73, 647, name_lines[0].strip())
    can.setFont("Times-Roman", 12)
    for i, line in enumerate(name_lines[1:], start=1):
        if line.strip():
            can.drawString(73, 647 - (i * 14), line.strip())
    date = format_date_ddmmyyyy(data.get("date", ""))
    from_date = format_date_ddmmyyyy(data.get("from_date", ""))
    to_date = format_date_ddmmyyyy(data.get("to_date", ""))
    can.setFont("Times-Roman", 11)
    can.drawString(467, 711, date)
    can.drawString(310, 542, from_date)
    can.drawString(385, 542, to_date)
    y_start, step = 477, 17
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
    can.setFont("Times-Bold", 12)
    can.drawString(295, 340, str(data.get("total", "")))
    can.save()
    packet.seek(0)
    return packet

def fill_pdf(template_path, data):
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

# Insert into Supabase
def insert_into_db(data):
    try:
        response = supabase.table("pdf_records").insert({
            "name": data.get("name"),
            "date": data.get("date"),
            "from_date": data.get("from_date"),
            "to_date": data.get("to_date"),
            "cf_charges": data.get("cf_charges"),
            "godown_rent": data.get("godown_rent"),
            "courier_charges": data.get("courier_charges"),
            "electric_bill": data.get("electric_bill"),
            "internet_charges": data.get("internet_charges"),
            "local_freight": data.get("local_freight"),
            "labour_charges": data.get("labour_charges"),
            "hamali_charges": data.get("hamali_charges"),
            "total": data.get("total"),
        }).execute()
        print("✅ Inserted into Supabase:", response)
    except Exception as e:
        print("❌ Supabase insert failed:", str(e))

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
    insert_into_db(data)
    pdf_bytes = fill_pdf("template.pdf", data)
    user_name = str(data.get("name", "document")).split("\n")[0].strip().replace(" ", "_")
    filename = f"{user_name}.pdf"
    return send_file(pdf_bytes, as_attachment=True, download_name=filename, mimetype="application/pdf")

@app.route("/records", methods=["GET"])
def records():
    try:
        response = supabase.table("pdf_records").select("*").order("created_at", desc=True).execute()
        rows = response.data
    except Exception as e:
        return f"<h1>❌ Failed to fetch records: {str(e)}</h1>"
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>Records</title>
      <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-100 p-8">
      <div class="max-w-6xl mx-auto bg-white shadow-lg rounded-xl p-6">
        <h1 class="text-2xl font-bold text-green-600 mb-4">📊 Stored Records</h1>
        <table class="w-full border border-gray-300 rounded-lg overflow-hidden">
          <thead class="bg-gray-200">
            <tr>
              <th class="px-4 py-2 border">ID</th>
              <th class="px-4 py-2 border">Name</th>
              <th class="px-4 py-2 border">Date</th>
              <th class="px-4 py-2 border">From</th>
              <th class="px-4 py-2 border">To</th>
              <th class="px-4 py-2 border">Total</th>
              <th class="px-4 py-2 border">Created At</th>
            </tr>
          </thead>
          <tbody>
    """
    for row in rows:
        html += f"""
        <tr class="hover:bg-gray-50">
          <td class="px-4 py-2 border">{row.get("id")}</td>
          <td class="px-4 py-2 border">{row.get("name")}</td>
          <td class="px-4 py-2 border">{row.get("date")}</td>
          <td class="px-4 py-2 border">{row.get("from_date")}</td>
          <td class="px-4 py-2 border">{row.get("to_date")}</td>
          <td class="px-4 py-2 border">{row.get("total")}</td>
          <td class="px-4 py-2 border">{row.get("created_at")}</td>
        </tr>
        """
    html += """
          </tbody>
        </table>
        <div class="mt-6 text-center">
          <a href="/" class="text-blue-600 underline">⬅ Back to Form</a>
        </div>
      </div>
    </body>
    </html>
    """
    return html