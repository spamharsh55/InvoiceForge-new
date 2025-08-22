# api/index.py
from flask import Flask, render_template_string, request, send_file, redirect, url_for
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from PyPDF2 import PdfReader, PdfWriter
import io
import os
import json
from datetime import datetime
from supabase import create_client, Client

# ----------------------------- App & Supabase ----------------------------- #
app = Flask(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in environment")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# IMPORTANT: template.pdf is in project root (not in /api)

TEMPLATE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "template.pdf"))
# Page size is 612 x 792 (US Letter) in points
PAGE_W, PAGE_H = letter  # (612.0, 792.0)

# ----------------------------- Shared HTML ----------------------------- #
BASE_HEAD = """
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <title>{{ title }}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <script src="https://cdn.tailwindcss.com"></script>
  <script>tailwind.config = { darkMode: 'class' };</script>
</head>
"""

# ----------------------------- Form (Create/Edit) ----------------------------- #
HTML_FORM = BASE_HEAD + """
<body class="bg-gray-900 text-white min-h-screen flex items-center justify-center font-sans">
  <div class="w-full max-w-5xl bg-gray-800 rounded-2xl shadow-lg p-8">
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-3xl font-bold text-green-400">{{ header }}</h1>
      <div class="flex gap-2">
        <a href="{{ url_for('records') }}" class="px-4 py-2 bg-blue-600 rounded-lg hover:bg-blue-700">View Records</a>
        <a href="{{ url_for('form') }}" class="px-4 py-2 bg-slate-600 rounded-lg hover:bg-slate-700">New</a>
      </div>
    </div>

    <form method="post" action="{{ action_url }}" class="space-y-6" id="bill-form">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <label class="block text-gray-300 font-medium mb-1">Name & Address</label>
          <textarea name="name" class="w-full border border-gray-600 rounded-lg p-3 focus:ring-2 focus:ring-green-400 bg-gray-700 text-white" rows="3" required>{{ data.get('name','') }}</textarea>
        </div>
        <div class="grid grid-cols-1 gap-6">
          <div>
            <label class="block text-gray-300 font-medium mb-1">Date</label>
            <input type="date" name="date" id="date" value="{{ data.get('date','') }}" class="w-full border border-gray-600 rounded-lg p-3 focus:ring-2 focus:ring-green-400 bg-gray-700 text-white" required>
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-gray-300 font-medium mb-1">From</label>
              <input type="date" id="from_date" name="from_date" value="{{ data.get('from_date','') }}" class="w-full border border-gray-600 rounded-lg p-3 focus:ring-2 focus:ring-green-400 bg-gray-700 text-white" required>
            </div>
            <div>
              <label class="block text-gray-300 font-medium mb-1">To</label>
              <input type="date" id="to_date" name="to_date" value="{{ data.get('to_date','') }}" class="w-full border border-gray-600 rounded-lg p-3 focus:ring-2 focus:ring-green-400 bg-gray-700 text-white" required>
            </div>
          </div>
        </div>
      </div>

      <!-- Dynamic Charges Table -->
      <div class="overflow-x-auto">
        <table class="w-full border border-gray-600 rounded-lg overflow-hidden text-sm" id="charges-table">
          <thead class="bg-gray-700">
            <tr>
              <th class="px-4 py-2 border border-gray-600 text-left">Charge Type</th>
              <th class="px-4 py-2 border border-gray-600 text-right">Amount</th>
              <th class="px-4 py-2 border border-gray-600 text-left">Remarks</th>
              <th class="px-4 py-2 border border-gray-600">Action</th>
            </tr>
          </thead>
          <tbody id="charges-body">
            <!-- Rows will be populated from server or defaults -->
          </tbody>
        </table>
      </div>

      <div class="flex items-center justify-between gap-4">
        <button type="button" id="add-row" class="px-4 py-2 bg-emerald-600 rounded-lg hover:bg-emerald-700">➕ Add Charge</button>
        <div class="flex-1"></div>
        <div class="w-60">
          <label class="block text-gray-300 font-medium mb-1">Total</label>
          <input name="total" id="total" value="{{ data.get('total','') }}" class="w-full border border-gray-600 rounded-lg p-3 bg-gray-700 text-white text-right" readonly required>
        </div>
      </div>

      <div class="flex justify-center gap-4">
        <button type="submit" class="px-6 py-3 bg-green-600 text-white rounded-lg shadow hover:bg-green-700 transition">
          {{ submit_label }}
        </button>
        <a href="{{ url_for('records') }}" class="px-6 py-3 bg-blue-600 text-white rounded-lg shadow hover:bg-blue-700 transition">
          View Records
        </a>
      </div>

      <!-- Hidden bootstrap of existing charges from server -->
      <input type="hidden" id="bootstrap-charges" value='{{ charges_json|tojson }}' />
    </form>
  </div>

  <script>
    const defaultCharges = [
      "C & F CHARGES",
      "GODOWN RENT",
      "COURIER CHARGES",
      "ELECTRIC BILL",
      "INTERNET CHARGES",
      "LOCAL FREIGHT",
      "LABOUR CHARGES",
      "HAMALI CHARGES",
    ];

    function addRow(type = "", amount = "", remark = "") {
      const tbody = document.getElementById("charges-body");
      const tr = document.createElement("tr");
      tr.className = "hover:bg-gray-700";
      tr.innerHTML = `
        <td class="px-3 py-2 border border-gray-700">
          <input type="text" name="charge_type[]" value="${type}" placeholder="Charge type" class="w-full border border-gray-600 rounded p-2 bg-gray-700 text-white">
        </td>
        <td class="px-3 py-2 border border-gray-700 text-right">
          <input type="number" step="0.01" name="charge_amount[]" value="${amount}" class="w-full border border-gray-600 rounded p-2 bg-gray-700 text-right text-green-300" oninput="recomputeTotal()">
        </td>
        <td class="px-3 py-2 border border-gray-700">
          <input type="text" name="charge_remark[]" value="${remark}" placeholder="Remark (optional)" class="w-full border border-gray-600 rounded p-2 bg-gray-700 text-white">
        </td>
        <td class="px-3 py-2 border border-gray-700 text-center">
          <button type="button" class="px-2 py-1 bg-red-600 rounded hover:bg-red-700" onclick="this.closest('tr').remove(); recomputeTotal();">❌</button>
        </td>
      `;
      tbody.appendChild(tr);
    }

    function recomputeTotal() {
      const amounts = Array.from(document.querySelectorAll('input[name="charge_amount[]"]'))
        .map(i => parseFloat(i.value || "0") || 0);
      const total = amounts.reduce((a,b)=>a+b, 0);
      document.getElementById("total").value = total.toFixed(2);
    }

    // Prefill for create mode
    (function init() {
      const isCreate = "{{ is_create|default(True) }}";
      const dt = document.getElementById("date");
      if (isCreate === "True" && dt && !dt.value) {
        dt.value = new Date().toISOString().split("T")[0];
      }
      const boot = document.getElementById("bootstrap-charges").value;
      let charges = [];
      try { charges = JSON.parse(boot) || []; } catch(e) { charges = []; }

      if (charges.length) {
        charges.forEach(ch => addRow(ch.type || "", ch.amount || "", ch.remark || ""));
      } else {
        defaultCharges.forEach(label => addRow(label, "", ""));
      }
      recomputeTotal();

      document.getElementById("add-row").addEventListener("click", () => addRow("", "", ""));
    })();

    // Date validation
    document.addEventListener("input", () => {
      let from = document.getElementById("from_date").value;
      let to = document.getElementById("to_date").value;
      const toEl = document.getElementById("to_date");
      if (from && to && to < from) {
        toEl.setCustomValidity("To Date cannot be earlier than From Date");
      } else {
        toEl.setCustomValidity("");
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
            <td class="px-3 py-2 border border-gray-700 text-right">{{ '%.2f'|format(r.get('total') or 0) }}</td>
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

def to_number(val):
    try:
        return float(val)
    except Exception:
        return 0.0

def compute_total_from_charges(charges):
    return round(sum(to_number(ch.get("amount", 0)) for ch in (charges or [])), 2)

def normalize_charges_from_request(form):
    types = form.getlist("charge_type[]")
    amounts = form.getlist("charge_amount[]")
    remarks = form.getlist("charge_remark[]")
    charges = []
    for t, a, r in zip(types, amounts, remarks):
        t = (t or "").strip()
        if t == "" and (a or "").strip() == "" and (r or "").strip() == "":
            continue
        amt = to_number(a)
        charges.append({"type": t, "amount": amt, "remark": r or ""})
    return charges

def migrate_row_to_charges_if_needed(row):
    """
    Backward compatibility: if a row doesn't have JSON charges but has old columns,
    convert them into a charges array for UI/PDF usage.
    """
    if row.get("charges"):
        return row["charges"]

    pairs = [
        ("C & F CHARGES", "cf_charges", "cf_remarks"),
        ("GODOWN RENT", "godown_rent", "godown_remarks"),
        ("COURIER CHARGES", "courier_charges", "courier_remarks"),
        ("ELECTRIC BILL", "electric_bill", "electric_remarks"),
        ("INTERNET CHARGES", "internet_charges", "internet_remarks"),
        ("LOCAL FREIGHT", "local_freight", "local_remarks"),
        ("LABOUR CHARGES", "labour_charges", "labour_remarks"),
        ("HAMALI CHARGES", "hamali_charges", "hamali_remarks"),
    ]
    charges = []
    for label, amount_key, remark_key in pairs:
        amount = row.get(amount_key)
        remark = row.get(remark_key)
        if amount is not None and str(amount).strip() not in ("", "None", "null"):
            charges.append({"type": label, "amount": to_number(amount), "remark": remark or ""})
    return charges

# ----------------------------- PDF Generation ----------------------------- #
def create_overlay_pdf(data):
  buf = io.BytesIO()
  can = canvas.Canvas(buf, pagesize=(PAGE_W, PAGE_H))

  # Header - Name & Address
  name_lines = str(data.get("name", "")).splitlines()
  can.setFont("Times-Bold", 12)
  if name_lines:
      can.drawString(73, 656, name_lines[0].strip())
  can.setFont("Times-Roman", 12)
  for i, line in enumerate(name_lines[1:], start=1):
      if line.strip():
          can.drawString(73, 656 - (i * 14), line.strip())

  # Dates
  date = format_date_ddmmyyyy(data.get("date", ""))
  from_date = format_date_ddmmyyyy(data.get("from_date", ""))
  to_date = format_date_ddmmyyyy(data.get("to_date", ""))
  can.setFont("Times-Roman", 11)
  can.drawString(467, 715, date)
  can.drawString(310, 547, from_date)
  can.drawString(385, 547, to_date)

  # ---- Dynamic Charges Table ----
  charges = data.get("charges") or []

  # ✅ Filter out empty/zero charges
  filtered_charges = [
      ch for ch in charges
      if (str(ch.get("type", "")).strip() != "" or str(ch.get("remark", "")).strip() != "")
      and to_number(ch.get("amount", 0)) > 0
  ]

  # Build table data (header + rows + total)
  table_data = [["SR", "PARTICULAR", "AMOUNT", "REMARK"]]
  for i, ch in enumerate(filtered_charges, start=1):
      table_data.append([
          str(i),
          str(ch.get("type", "")),
          f"{to_number(ch.get('amount', 0)):.2f}",
          str(ch.get("remark", "")),
      ])
  table_data.append(["", "TOTAL", f"{to_number(data.get('total', 0)):.2f}", ""])

  # --- Fixed table layout ---
  TABLE_LEFT = 60
  TABLE_TOP_Y = 510
  TABLE_WIDTHS = [40, 230, 90, 132]   # fixed column widths
  ROW_HEIGHT = 18                     # fixed row height
  FONT_SIZE_BODY = 10
  FONT_SIZE_HEADER = 11

  num_rows = len(table_data)

  tbl = Table(table_data, colWidths=TABLE_WIDTHS, rowHeights=[ROW_HEIGHT] * num_rows)
  tbl.setStyle(TableStyle([
      ("GRID", (0,0), (-1,-1), 0.8, colors.black),
      ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
      ("ALIGN", (0,0), (0,-1), "CENTER"),   # SR centered

      # Header
      ("FONTNAME", (0,0), (-1,0), "Times-Bold"),
      ("FONTSIZE", (0,0), (-1,0), FONT_SIZE_HEADER),
      ("BACKGROUND", (0,0), (-1,0), colors.white),
      ("TEXTCOLOR", (0,0), (-1,0), colors.black),

      # Body
      ("FONTNAME", (0,1), (-1,-1), "Times-Roman"),
      ("FONTSIZE", (0,1), (-1,-1), FONT_SIZE_BODY),

      # TOTAL row
      ("FONTNAME", (1,-1), (2,-1), "Times-Bold"),
      ("ALIGN", (1,-1), (1,-1), "RIGHT"),
      ("ALIGN", (2,1), (2,-1), "RIGHT"),
      ("ALIGN", (2,-1), (2,-1), "RIGHT"),
      ("BACKGROUND", (0,-1), (-1,-1), colors.white),
      ("TEXTCOLOR", (0,-1), (-1,-1), colors.black),
      ("SPAN", (0,-1), (0,-1)),
  ]))

  # Always draw starting from fixed top Y
  table_height = num_rows * ROW_HEIGHT
  table_bottom_y = TABLE_TOP_Y - table_height
  tbl.wrapOn(can, TABLE_LEFT, table_bottom_y)
  tbl.drawOn(can, TABLE_LEFT, table_bottom_y)

  # --- Add Bank Details Note ---
  note_text = """Please credit the expenses in our account
  Account Name :- Sai Agro Inputs
  Account No. :- 921020042670090
  IFSC Code :- UTIB0000749
  Bank :- Axis Bank
  Branch :- Amankha Plot Road Akola"""

  can.setFont("Times-Roman", 12)  # same as table body
  text_x = TABLE_LEFT
  text_y = table_bottom_y - 40    # 40 points gap below the table

  for line in note_text.splitlines():
      can.drawString(text_x, text_y, line)
      text_y -= 14   # line spacing

  can.save()
  buf.seek(0)
  return buf

def fill_pdf_with_overlay(template_path, data):
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

# ----------------------------- DB helpers ----------------------------- #
def insert_record(data):
    """
    data must contain: name, date, from_date, to_date, charges (list), total (float)
    """
    payload = {
        "name": data.get("name"),
        "date": data.get("date"),
        "from_date": data.get("from_date"),
        "to_date": data.get("to_date"),
        "charges": data.get("charges"),  # JSON array
        "total": data.get("total"),
    }
    # Optional: keep old columns in case your table still has them (set null)
    return supabase.table("pdf_records").insert(payload).execute()

def update_record_db(record_id, data):
    payload = {
        "name": data.get("name"),
        "date": data.get("date"),
        "from_date": data.get("from_date"),
        "to_date": data.get("to_date"),
        "charges": data.get("charges"),
        "total": data.get("total"),
    }
    return supabase.table("pdf_records").update(payload).eq("id", record_id).execute()

def fetch_one(record_id):
    res = supabase.table("pdf_records").select("*").eq("id", record_id).single().execute()
    return res.data

# ----------------------------- Routes ----------------------------- #
@app.route("/", methods=["GET"])
def form():
    context = {
        "title": "PDF Generator",
        "header": "📄 PDF Generator",
        "action_url": url_for("generate"),
        "submit_label": "Generate",
        "data": {},
        "is_create": True,
        "charges_json": [],  # will be defaulted in JS if empty
    }
    return render_template_string(HTML_FORM, **context)

@app.route("/generate", methods=["POST"])
def generate():
    # Gather basic fields
    name = request.form.get("name", "")
    date = request.form.get("date", "")
    from_date = request.form.get("from_date", "")
    to_date = request.form.get("to_date", "")

    # Gather dynamic charges array
    charges = normalize_charges_from_request(request.form)
    total = compute_total_from_charges(charges)

    # Build record
    record = {
        "name": name,
        "date": date,
        "from_date": from_date,
        "to_date": to_date,
        "charges": charges,
        "total": total,
    }

    # Insert to DB (best-effort; do not fail PDF if DB fails)
    try:
        insert_record(record)
    except Exception as e:
        print("❌ Supabase insert failed:", e)

    # Build PDF
    pdf_bytes = fill_pdf_with_overlay(TEMPLATE_PATH, record)

    # File name
    user_name = (name or "document").split("\n")[0].strip().replace(" ", "_")
    filename = f"{user_name}.pdf"
    return send_file(pdf_bytes, as_attachment=True, download_name=filename, mimetype="application/pdf")

@app.route("/records", methods=["GET"])
def records():
    try:
        response = supabase.table("pdf_records").select("*").order("id", desc=True).execute()
        rows = response.data or []
        # Ensure total is computed for any legacy rows
        for r in rows:
            charges = migrate_row_to_charges_if_needed(r)
            r["total"] = r.get("total") or compute_total_from_charges(charges)
        grand_total = sum(float(r.get("total") or 0) for r in rows)
    except Exception as e:
        print("❌ Failed to fetch from Supabase:", e)
        rows, grand_total = [], 0.0
    return render_template_string(HTML_RECORDS, title="Database Records", rows=rows, grand_total=grand_total)

@app.route("/print/<int:record_id>", methods=["GET"])
def print_record(record_id: int):
    record = fetch_one(record_id)
    if not record:
        return "Record not found", 404

    # Normalize for legacy rows
    charges = migrate_row_to_charges_if_needed(record)
    total = record.get("total") or compute_total_from_charges(charges)

    record_for_pdf = {
        "name": record.get("name", ""),
        "date": record.get("date", ""),
        "from_date": record.get("from_date", ""),
        "to_date": record.get("to_date", ""),
        "charges": charges,
        "total": total,
    }

    pdf_bytes = fill_pdf_with_overlay(TEMPLATE_PATH, record_for_pdf)
    user_name = str(record.get("name", "document")).split("\n")[0].strip().replace(" ", "_") or f"record_{record_id}"
    filename = f"{user_name}.pdf"
    return send_file(pdf_bytes, as_attachment=True, download_name=filename, mimetype="application/pdf")

@app.route("/edit/<int:record_id>", methods=["GET"])
def edit_record(record_id: int):
    record = fetch_one(record_id)
    if not record:
        return "Record not found", 404

    # Prepare charges JSON for the form bootstrap
    charges = migrate_row_to_charges_if_needed(record)
    context = {
        "title": f"Edit Record #{record_id}",
        "header": f"✏️ Edit Record #{record_id}",
        "action_url": url_for("update_record", record_id=record_id),
        "submit_label": "Save Changes",
        "data": {
            "name": record.get("name", ""),
            "date": record.get("date", ""),
            "from_date": record.get("from_date", ""),
            "to_date": record.get("to_date", ""),
            "total": record.get("total") or compute_total_from_charges(charges),
        },
        "is_create": False,
        "charges_json": charges,
    }
    return render_template_string(HTML_FORM, **context)

@app.route("/update/<int:record_id>", methods=["POST"])
def update_record(record_id: int):
    # Gather fields
    name = request.form.get("name", "")
    date = request.form.get("date", "")
    from_date = request.form.get("from_date", "")
    to_date = request.form.get("to_date", "")
    charges = normalize_charges_from_request(request.form)
    total = compute_total_from_charges(charges)

    try:
        update_record_db(record_id, {
            "name": name,
            "date": date,
            "from_date": from_date,
            "to_date": to_date,
            "charges": charges,
            "total": total,
        })
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

# ----------------------------- Local Dev (Replit) ----------------------------- #
# Vercel will import app via WSGI from this module; running locally also works.
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)