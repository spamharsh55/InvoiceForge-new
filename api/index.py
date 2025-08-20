from flask import Flask, render_template_string, request, send_file, redirect, url_for
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter
import io
import os
from datetime import datetime
from supabase import create_client, Client

# ----------------------------- App & Supabase ----------------------------- #
app = Flask(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "template.pdf")

# ----------------------------- Shared HTML ----------------------------- #
BASE_HEAD = """
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <title>{{ title }}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>tailwind.config = { darkMode: 'class' };</script>
</head>
"""

# ----------------------------- Form (Create/Edit) ----------------------------- #
HTML_FORM = BASE_HEAD + """
<body class="bg-gray-900 text-white min-h-screen flex items-center justify-center font-sans">
  <div class="w-full max-w-4xl bg-gray-800 rounded-2xl shadow-lg p-8">
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-3xl font-bold text-green-400">{{ header }}</h1>
      <div class="flex gap-2">
        <a href="{{ url_for('records') }}" class="px-4 py-2 bg-blue-600 rounded-lg hover:bg-blue-700">View Records</a>
        <a href="{{ url_for('form') }}" class="px-4 py-2 bg-slate-600 rounded-lg hover:bg-slate-700">New</a>
      </div>
    </div>

    <form method="post" action="{{ action_url }}" class="space-y-6">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <label class="block text-gray-300 font-medium mb-1">Name & Address</label>
          <textarea name="name" class="w-full border border-gray-600 rounded-lg p-3 focus:ring-2 focus:ring-green-400 bg-gray-700 text-white" rows="3" required>{{ data.get('name','') }}</textarea>
        </div>
        <div>
          <label class="block text-gray-300 font-medium mb-1">Date</label>
          <input type="date" name="date" id="date" value="{{ data.get('date','') }}" class="w-full border border-gray-600 rounded-lg p-3 focus:ring-2 focus:ring-green-400 bg-gray-700 text-white" required>
        </div>
        <div>
          <label class="block text-gray-300 font-medium mb-1">From</label>
          <input type="date" id="from_date" name="from_date" value="{{ data.get('from_date','') }}" class="w-full border border-gray-600 rounded-lg p-3 focus:ring-2 focus:ring-green-400 bg-gray-700 text-white" required>
        </div>
        <div>
          <label class="block text-gray-300 font-medium mb-1">To</label>
          <input type="date" id="to_date" name="to_date" value="{{ data.get('to_date','') }}" class="w-full border border-gray-600 rounded-lg p-3 focus:ring-2 focus:ring-green-400 bg-gray-700 text-white" required>
        </div>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full border border-gray-600 rounded-lg overflow-hidden">
          <thead class="bg-gray-700">
            <tr>
              <th class="px-4 py-2 border border-gray-600">Charge Type</th>
              <th class="px-4 py-2 border border-gray-600">Amount</th>
              <th class="px-4 py-2 border border-gray-600">Remarks</th>
            </tr>
          </thead>
          <tbody>
            {% for charge, remarks in charge_fields %}
            <tr class="hover:bg-gray-600">
              <td class="px-4 py-2 border border-gray-600 text-gray-200">{{ charge.replace('_', ' ').title() }}</td>
              <td class="px-4 py-2 border border-gray-600">
                <input type="number" step="0.01" name="{{ charge }}" value="{{ data.get(charge,'') }}" class="w-full border border-green-500 rounded-lg p-2 focus:ring-2 focus:ring-green-400 bg-gray-700 text-green-300" oninput="updateTotal()">
              </td>
              <td class="px-4 py-2 border border-gray-600">
                <input type="text" name="{{ remarks }}" value="{{ data.get(remarks,'') }}" class="w-full border border-blue-500 rounded-lg p-2 focus:ring-2 focus:ring-blue-400 bg-gray-700 text-blue-300">
              </td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>

      <div>
        <label class="block text-gray-300 font-medium mb-1">Total</label>
        <input name="total" value="{{ data.get('total','') }}" class="w-full border border-gray-600 rounded-lg p-3 bg-gray-700 text-white" readonly required>
      </div>

      <div class="flex justify-center gap-4">
        <button type="submit" class="px-6 py-3 bg-green-600 text-white rounded-lg shadow hover:bg-green-700 transition">
          {{ submit_label }}
        </button>
        <a href="{{ url_for('records') }}" class="px-6 py-3 bg-blue-600 text-white rounded-lg shadow hover:bg-blue-700 transition">
          View Records
        </a>
      </div>
    </form>
  </div>

  <script>
    function updateTotal() {
      let fields = [
        "cf_charges", "godown_rent", "courier_charges", "electric_bill",
        "internet_charges", "local_freight", "labour_charges", "hamali_charges"
      ];
      let total = 0;
      fields.forEach(id => {
        let el = document.querySelector(`[name="${id}"]`);
        let val = parseFloat(el && el.value) || 0;
        total += val;
      });
      let totalEl = document.querySelector('[name="total"]');
      if (totalEl) totalEl.value = total.toFixed(2);
    }

    // Prefill today's date for create mode
    (function(){
      const isCreate = "{{ is_create|default(True) }}";
      if (isCreate === "True") {
        const dt = document.getElementById("date");
        if (dt && !dt.value) dt.value = new Date().toISOString().split("T")[0];
      }
    })();

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
</body>
</html>
"""

# ----------------------------- Records Page ----------------------------- #
HTML_RECORDS = BASE_HEAD + """
<body class="bg-gray-900 text-white min-h-screen font-sans">
  <div class="max-w-6xl mx-auto p-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-3xl font-bold text-green-400">📊 Database Records</h1>
      <a href="{{ url_for('form') }}" class="px-4 py-2 bg-slate-600 rounded-lg hover:bg-slate-700">+ New</a>
    </div>

    <div class="bg-gray-800 rounded-2xl shadow-lg p-4 overflow-x-auto">
      <table class="w-full border border-gray-700 rounded-lg overflow-hidden text-sm">
        <thead class="bg-gray-700">
          <tr>
            <th class="px-3 py-2 border border-gray-600">ID</th>
            <th class="px-3 py-2 border border-gray-600">Name</th>
            <th class="px-3 py-2 border border-gray-600">Date</th>
            <th class="px-3 py-2 border border-gray-600">From</th>
            <th class="px-3 py-2 border border-gray-600">To</th>
            <th class="px-3 py-2 border border-gray-600 text-right">Total</th>
            <th class="px-3 py-2 border border-gray-600">Actions</th>
          </tr>
        </thead>
        <tbody>
          {% for r in rows %}
          <tr class="hover:bg-gray-700">
            <td class="px-3 py-2 border border-gray-700">{{ r.get('id','') }}</td>
            <td class="px-3 py-2 border border-gray-700 whitespace-pre-line">{{ (r.get('name') or '').split('\\n')[0] }}</td>
            <td class="px-3 py-2 border border-gray-700">{{ r.get('date','') }}</td>
            <td class="px-3 py-2 border border-gray-700">{{ r.get('from_date','') }}</td>
            <td class="px-3 py-2 border border-gray-700">{{ r.get('to_date','') }}</td>
            <td class="px-3 py-2 border border-gray-700 text-right">{{ r.get('total','') }}</td>
            <td class="px-3 py-2 border border-gray-700">
              <div class="flex gap-2">
                <a href="{{ url_for('print_record', record_id=r.get('id')) }}" class="px-3 py-1 bg-emerald-600 rounded hover:bg-emerald-700">Print</a>
                <a href="{{ url_for('edit_record', record_id=r.get('id')) }}" class="px-3 py-1 bg-blue-600 rounded hover:bg-blue-700">Edit</a>
                <form method="post" action="{{ url_for('delete_record', record_id=r.get('id')) }}" onsubmit="return confirm('Delete this record?');">
                  <button class="px-3 py-1 bg-red-600 rounded hover:bg-red-700" type="submit">Delete</button>
                </form>
              </div>
            </td>
          </tr>
          {% endfor %}
          {% if not rows %}
          <tr>
            <td colspan="7" class="px-3 py-6 text-center text-gray-400">No records yet.</td>
          </tr>
          {% endif %}
        </tbody>
      </table>
    </div>

    <div class="mt-4 text-right text-xl font-semibold text-green-400">
      Grand Total: {{ "%.2f"|format(grand_total) }}
    </div>

    <div class="mt-6">
      <a href="{{ url_for('form') }}" class="px-4 py-2 bg-green-600 rounded-lg hover:bg-green-700">⬅ Back to Form</a>
    </div>
  </div>
</body>
</html>
"""

# ----------------------------- Helpers ----------------------------- #
def format_date_ddmmyyyy(date_str):
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%d-%m-%Y")
    except Exception:
        return date_str or ""

def safe_number(val):
    try:
        return float(val) if str(val).strip() not in ("", "None", "null") and val is not None else None
    except Exception:
        return None

def charge_pairs():
    return [
        ("cf_charges", "cf_remarks"),
        ("godown_rent", "godown_remarks"),
        ("courier_charges", "courier_remarks"),
        ("electric_bill", "electric_remarks"),
        ("internet_charges", "internet_remarks"),
        ("local_freight", "local_remarks"),
        ("labour_charges", "labour_remarks"),
        ("hamali_charges", "hamali_remarks"),
    ]

def create_overlay(data):
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(612, 792))

    # Name & address
    name_lines = str(data.get("name", "")).splitlines()
    can.setFont("Times-Bold", 12)
    if name_lines:
        can.drawString(73, 647, name_lines[0].strip())
    can.setFont("Times-Roman", 12)
    for i, line in enumerate(name_lines[1:], start=1):
        if line.strip():
            can.drawString(73, 647 - (i * 14), line.strip())

    # Dates
    date = format_date_ddmmyyyy(data.get("date", ""))
    from_date = format_date_ddmmyyyy(data.get("from_date", ""))
    to_date = format_date_ddmmyyyy(data.get("to_date", ""))
    can.setFont("Times-Roman", 11)
    can.drawString(467, 711, date)
    can.drawString(310, 542, from_date)
    can.drawString(385, 542, to_date)

    # Charges & remarks
    y_start = 477
    step = 17
    can.setFont("Times-Roman", 11)
    for i, (charge, remark) in enumerate(charge_pairs()):
        y = y_start - (i * step)
        can.drawString(310, y, str(data.get(charge, "") or ""))
        can.drawString(390, y, str(data.get(remark, "") or ""))

    # Total
    can.setFont("Times-Bold", 12)
    can.drawString(295, 340, str(data.get("total", "") or ""))

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

def compute_total(data_dict):
    fields = [
        "cf_charges", "godown_rent", "courier_charges", "electric_bill",
        "internet_charges", "local_freight", "labour_charges", "hamali_charges"
    ]
    total = 0.0
    for f in fields:
        try:
            total += float(data_dict.get(f) or 0)
        except Exception:
            pass
    return round(total, 2)

def insert_into_db(data):
  try:
      response = supabase.table("pdf_records").insert({
          "name": data.get("name"),
          "date": data.get("date"),
          "from_date": data.get("from_date"),
          "to_date": data.get("to_date"),
          "cf_charges": safe_number(data.get("cf_charges")),
          "godown_rent": safe_number(data.get("godown_rent")),
          "courier_charges": safe_number(data.get("courier_charges")),
          "electric_bill": safe_number(data.get("electric_bill")),
          "internet_charges": safe_number(data.get("internet_charges")),
          "local_freight": safe_number(data.get("local_freight")),
          "labour_charges": safe_number(data.get("labour_charges")),
          "hamali_charges": safe_number(data.get("hamali_charges")),
          "total": safe_number(data.get("total")),
      }).execute()
      print("✅ Inserted into Supabase:", response)
  except Exception as e:
      print("❌ Supabase insert failed:", str(e))

def update_db(record_id, data):
    payload = {
        "name": data.get("name"),
        "date": data.get("date"),
        "from_date": data.get("from_date"),
        "to_date": data.get("to_date"),
        "cf_charges": safe_number(data.get("cf_charges")),
        "godown_rent": safe_number(data.get("godown_rent")),
        "courier_charges": safe_number(data.get("courier_charges")),
        "electric_bill": safe_number(data.get("electric_bill")),
        "internet_charges": safe_number(data.get("internet_charges")),
        "local_freight": safe_number(data.get("local_freight")),
        "labour_charges": safe_number(data.get("labour_charges")),
        "hamali_charges": safe_number(data.get("hamali_charges")),
        "cf_remarks": data.get("cf_remarks"),
        "godown_remarks": data.get("godown_remarks"),
        "courier_remarks": data.get("courier_remarks"),
        "electric_remarks": data.get("electric_remarks"),
        "internet_remarks": data.get("internet_remarks"),
        "local_remarks": data.get("local_remarks"),
        "labour_remarks": data.get("labour_remarks"),
        "hamali_remarks": data.get("hamali_remarks"),
        "total": safe_number(data.get("total")),
    }
    return supabase.table("pdf_records").update(payload).eq("id", record_id).execute()

def fetch_record(record_id):
    return supabase.table("pdf_records").select("*").eq("id", record_id).single().execute().data

# ----------------------------- Routes ----------------------------- #
@app.route("/", methods=["GET"])
def form():
    charge_fields = charge_pairs()
    context = {
        "title": "PDF Generator",
        "header": "📄 PDF Generator",
        "action_url": url_for("generate"),
        "submit_label": "Generate",
        "data": {},
        "charge_fields": charge_fields,
        "is_create": True,
    }
    return render_template_string(HTML_FORM, **context)

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

  return send_file(pdf_bytes,
                   as_attachment=True,
                   download_name=filename,
                   mimetype="application/pdf")

@app.route("/records", methods=["GET"])
@app.route("/records", methods=["GET"])
def records():
    try:
        response = supabase.table("pdf_records").select("*").order("id", desc=True).execute()
        rows = response.data or []
        # Compute grand total
        grand_total = sum(float(r.get("total") or 0) for r in rows)
    except Exception as e:
        print("❌ Failed to fetch from Supabase:", e)
        rows, grand_total = [], 0
    return render_template_string(HTML_RECORDS, title="Database Records", rows=rows, grand_total=grand_total)


@app.route("/print/<int:record_id>", methods=["GET"])
def print_record(record_id: int):
    record = fetch_record(record_id)
    if not record:
        return "Record not found", 404
    # Ensure total is present/accurate
    if not record.get("total"):
        record["total"] = str(compute_total(record))
    pdf_bytes = fill_pdf(TEMPLATE_PATH, record)
    user_name = str(record.get("name", "document")).split("\n")[0].strip().replace(" ", "_") or f"record_{record_id}"
    filename = f"{user_name}.pdf"
    return send_file(pdf_bytes, as_attachment=True, download_name=filename, mimetype="application/pdf")

@app.route("/edit/<int:record_id>", methods=["GET"])
def edit_record(record_id: int):
    record = fetch_record(record_id)
    if not record:
        return "Record not found", 404
    charge_fields = charge_pairs()
    context = {
        "title": f"Edit Record #{record_id}",
        "header": f"✏️ Edit Record #{record_id}",
        "action_url": url_for("update_record", record_id=record_id),
        "submit_label": "Save Changes",
        "data": record,
        "charge_fields": charge_fields,
        "is_create": False,
    }
    return render_template_string(HTML_FORM, **context)

@app.route("/update/<int:record_id>", methods=["POST"])
def update_record(record_id: int):
    data = {key: request.form.get(key, "") for key in request.form}
    data["total"] = str(compute_total(data))
    try:
        update_db(record_id, data)
    except Exception as e:
        print("❌ Supabase update failed:", e)
    return redirect(url_for("records"))

@app.route("/delete/<int:record_id>", methods=["POST"])
def delete_record(record_id: int):
    try:
        supabase.table("pdf_records").delete().eq("id", record_id).execute()
    except Exception as e:
        print("❌ Supabase delete failed:", e)
    return redirect(url_for("records"))

# ----------------------------- Replit run ----------------------------- #
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
