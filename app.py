from flask import Flask, render_template, request, send_file
import io
import os
import psycopg2
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.lib.colors import HexColor, black
from reportlab.pdfbase.pdfmetrics import stringWidth
from PyPDF2 import PdfMerger
from num2words import num2words
from dotenv import load_dotenv
import math
from datetime import datetime
import logging

# ==============================
# Load Environment Variables
# ==============================
load_dotenv()

# === Logging ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask App
app = Flask(__name__)

# === Config ===
TEMP_FOLDER = "temp_invoices"
os.makedirs(TEMP_FOLDER, exist_ok=True)

# --- PostgreSQL Connection ---
def get_db_connection():
    # Fetch environment variables
    host = os.getenv("PG_HOST")
    database = os.getenv("PG_DB")
    user = os.getenv("PG_USER")
    password = os.getenv("PG_PASS")
    port = os.getenv("PG_PORT")

    # Check that all required variables are provided
    missing = [var for var, val in {
        "PG_HOST": host,
        "PG_DB": database,
        "PG_USER": user,
        "PG_PASS": password,
        "PG_PORT": port
    }.items() if not val]

    if missing:
        raise EnvironmentError(f"Missing required database environment variables: {', '.join(missing)}")

    # Convert port to int
    try:
        port = int(port)
    except ValueError:
        raise ValueError(f"Invalid PG_PORT value: {port}")

    # Connect to the database
    return psycopg2.connect(
        host=host,
        database=database,
        user=user,
        password=password,
        port=port
    )

# --- Initialize Database ---
def init_db():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS invoices (
                    id SERIAL PRIMARY KEY,
                    invoice_no VARCHAR(50) UNIQUE NOT NULL,
                    invoice_date VARCHAR(50),
                    state VARCHAR(50),
                    state_code VARCHAR(50),
                    delivery_challan_no VARCHAR(50),
                    delivery_challan_date VARCHAR(50),
                    transport_mode VARCHAR(50),
                    vehicle_no VARCHAR(50),
                    date_of_supply VARCHAR(50),
                    place_of_supply VARCHAR(50),
                    insurance_policy_no VARCHAR(50),
                    insurance_policy_date VARCHAR(50),
                    vendor_code VARCHAR(50),
                    po_no VARCHAR(50),
                    po_date VARCHAR(50),
                    invoiced_to_address TEXT,
                    invoiced_state VARCHAR(50),
                    invoiced_state_code VARCHAR(50),
                    invoiced_gstin VARCHAR(50),
                    consigned_to_address TEXT,
                    consigned_state VARCHAR(50),
                    consigned_state_code VARCHAR(50),
                    consigned_gstin VARCHAR(50)
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS invoice_items (
                    id SERIAL PRIMARY KEY,
                    invoice_id INT NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
                    item_desc TEXT,
                    item_hsn VARCHAR(50),
                    item_qty FLOAT,
                    item_rate FLOAT,
                    item_cgst FLOAT,
                    item_sgst FLOAT,
                    item_igst FLOAT
                )
            ''')
        conn.commit()

init_db()

# --- Helpers ---
def safe_float(val):
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0

def fmt_or_blank(val: float) -> str:
    return f"{val:.2f}" if val != 0 else ""


# ... (Paste all other drawing helper functions here:
#      draw_invoice_info_box, wrap_address_top_down_balanced,
#      draw_address_box, draw_state_gstin_box, draw_vendor_po_box,
#      draw_invoice_item_table, draw_three_column_box,
#      draw_terms_and_conditions) ...

def draw_invoice_info_box(c, x, y, width, row_height=11, invoice_data=None):
    col_width = width / 2
    info_box_height = row_height * 5

    c.setLineWidth(1)
    c.rect(x, y - info_box_height, width, info_box_height)
    c.line(x + col_width, y, x + col_width, y - info_box_height)

    label_x = x + 5
    value_x = x + col_width / 2 + 5
    base_y = y - 9

    invoice_data = invoice_data or {}

    left_labels = [
        ("INVOICE NO:", invoice_data.get("invoice_no", "")),
        ("DATE OF INVOICE:", invoice_data.get("invoice_date", "")),
        ("STATE:", invoice_data.get("state", "")),
        ("STATE CODE:", invoice_data.get("state_code", "")),
        ("Our Delivery Challan No.:", invoice_data.get("delivery_challan_no", ""))
    ]

    right_labels = [
        ("TRANSPORT MODE:", invoice_data.get("transport_mode", "")),
        ("VEHICLE NO:", invoice_data.get("vehicle_no", "")),
        ("DATE OF SUPPLY:", invoice_data.get("date_of_supply", "")),
        ("PLACE OF SUPPLY:", invoice_data.get("place_of_supply", "")),
        ("Insurance Policy No.:", invoice_data.get("insurance_policy_no", ""))
    ]
    right_sub = ("Dated:", invoice_data.get("insurance_policy_date", ""))

    c.setFont("Helvetica-Oblique", 8)
    for i, (label, value) in enumerate(left_labels):
        y_offset = base_y - i * row_height
        c.drawString(label_x, y_offset, label)
        if i == 4:
            c.drawString(label_x + 105, y_offset, value)
            c.drawString(label_x + 175, y_offset, "Date:")
            c.drawString(label_x + 205, y_offset, invoice_data.get("delivery_challan_date", ""))
        else:
            c.drawString(value_x, y_offset, value)

    for i, (label, value) in enumerate(right_labels):
        y_offset = base_y - i * row_height
        c.drawString(x + col_width + 5, y_offset, label)
        if i == 4:
            c.drawString(x + col_width + 95, y_offset, value)
            c.drawString(x + col_width + 200, y_offset, right_sub[0])
            c.drawString(x + col_width + 230, y_offset, right_sub[1])
        else:
            c.drawString(x + col_width + 90, y_offset, value)


def wrap_address_top_down_balanced(text, rows=4):
    parts = [part.strip() for part in text.split(',') if part.strip()]
    total = len(parts)
    if total == 0:
        return [""] * rows

    lines, i = [], 0
    for r in range(rows):
        remaining = total - i
        size = max(1, remaining // (rows - r)) if (rows - r) > 0 else 1
        line = ", ".join(parts[i:i + size])
        lines.append(line)
        i += size
        if i >= total:
            break
    while len(lines) < rows:
        lines.append("")
    return lines[:rows]


def draw_address_box(c, x, y, width, row_height=11, spacing=5, left_address="", right_address=""):
    col_width = width / 2
    address_rows = 4
    address_box_height = row_height * (address_rows + 1)

    y -= (spacing + address_box_height)

    c.setLineWidth(1)
    c.rect(x, y, width, address_box_height)
    c.line(x + col_width, y, x + col_width, y + address_box_height)

    c.setFont("Helvetica-Oblique", 8)
    c.setFillColorRGB(0.831, 0.282, 0.149)
    c.drawString(x + 5, y + address_box_height - row_height + 2, "Invoiced To,")
    c.drawString(x + col_width + 5, y + address_box_height - row_height + 2, "Consigned To,")

    c.setFont("Helvetica-BoldOblique", 8)
    c.setFillColorRGB(0, 0, 0)

    left_lines = wrap_address_top_down_balanced(left_address)
    right_lines = wrap_address_top_down_balanced(right_address)

    for i in range(address_rows):
        line_y = y + address_box_height - ((i + 2) * row_height) + 2
        if i < len(left_lines):
            c.drawString(x + 10, line_y, left_lines[i])
        if i < len(right_lines):
            c.drawString(x + col_width + 10, line_y, right_lines[i])

    return y


def draw_state_gstin_box(c, x, y, width, row_height=11,
                         left_state="", left_state_code="", left_gstin="",
                         right_state="", right_state_code="", right_gstin=""):
    col_width = width / 2
    rows = 3
    box_height = row_height * rows

    c.setLineWidth(1)
    c.rect(x, y - box_height, width, box_height)
    c.line(x + col_width, y - box_height, x + col_width, y)

    left_labels = ["STATE:", "STATE CODE:", "GSTIN/UNIQUE ID:"]
    right_labels = ["STATE:", "STATE CODE:", "GSTIN/UNIQUE ID:"]

    left_values = [left_state, left_state_code, left_gstin]
    right_values = [right_state, right_state_code, right_gstin]

    c.setFont("Helvetica-Oblique", 8)
    for i in range(rows):
        line_y = y - (i * row_height) - row_height + 3
        c.drawString(x + 5, line_y, f"{left_labels[i]} {left_values[i]}")
        c.drawString(x + col_width + 5, line_y, f"{right_labels[i]} {right_values[i]}")

    return y - box_height


def draw_vendor_po_box(c, x, y, width, row_height=11, spacing=5, invoice_data=None):
    box_height = row_height
    y -= (spacing + box_height)
    col_width = width / 3
    invoice_data = invoice_data or {}

    c.setLineWidth(1)
    c.rect(x, y, width, box_height)
    c.line(x + col_width, y, x + col_width, y + box_height)
    c.line(x + 2 * col_width, y, x + 2 * col_width, y + box_height)

    c.setFont("Helvetica-Oblique", 8)
    c.setFillColorRGB(0, 0, 0)
    c.drawString(x + 5, y + 3, f"Vendor Code: {invoice_data.get('vendor_code', '')}")
    c.drawString(x + col_width + 5, y + 3, f"P.O. No: {invoice_data.get('po_no', '')}")
    c.drawString(x + 2 * col_width + 5, y + 3, f"P.O. Date: {invoice_data.get('po_date', '')}")

    return y

def wrap_text(text, font_name, font_size, max_width):
    """
    Wraps text into lines that fit within max_width.
    """
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test_line = current_line + (" " if current_line else "") + word
        if stringWidth(test_line, font_name, font_size) <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines


def draw_invoice_item_table(c, x, y, width, header_height=24, row_height=14, items=None):
    orange = HexColor("#d14000")

    def format_item_value(value, value_type):
        num = safe_float(value)
        if value_type == 'qty' or value_type == 'percentage':
            return str(int(num)) if num != 0.0 else "0"
        elif value_type == 'rate':
            return f"{num:.2f}" if num != 0.0 else "0"
        elif value_type == 'amount':
            return f"{num:.2f}" if num != 0.0 else "0.00"
        else:
            return str(value if value is not None else "")

    def fmt_or_blank(value):
        num = safe_float(value)
        return f"{num:.2f}"

    column_widths = [
        7 * mm,   # NO.
        51 * mm,  # DESCRIPTION
        15 * mm,  # HSN/SAC
        10 * mm,  # QTY
        18 * mm,  # UNIT RATE
        18 * mm,  # TAXABLE VALUE
        27 * mm,  # CGST
        27 * mm,  # SGST
        27 * mm   # IGST
    ]
    col_x = [x]
    for w in column_widths:
        col_x.append(col_x[-1] + w)

    total_data_rows = 25
    table_height = header_height + (row_height * total_data_rows)
    header_top_y = y
    header_bottom_y = y - header_height
    header_middle_y = y - (header_height / 2)
    top_line_offset = header_height * 0.3
    bottom_line_offset = header_height * 0.2

    for i in range(len(col_x)):
        c.line(col_x[i], y, col_x[i], y - table_height)
    for i in [6, 7, 8]:
        mid = col_x[i] + (column_widths[i] / 2)
        c.line(col_x[i], header_middle_y, col_x[i + 1], header_middle_y)
        c.line(mid, header_middle_y, mid, y - table_height)
    c.line(x, y, col_x[-1], y)
    c.line(x, y - header_height, col_x[-1], y - header_height)

    c.setFont("Helvetica-Bold", 6.5)
    c.setFillColor(orange)
    c.drawCentredString((col_x[0] + col_x[1]) / 2, header_top_y - top_line_offset, "SR.")
    c.drawCentredString((col_x[0] + col_x[1]) / 2, header_bottom_y + bottom_line_offset, "NO.")
    c.drawCentredString((col_x[1] + col_x[2]) / 2, header_middle_y, "DESCRIPTION OF GOODS")
    c.drawCentredString((col_x[2] + col_x[3]) / 2, header_top_y - top_line_offset, "HSN / SAC")
    c.drawCentredString((col_x[2] + col_x[3]) / 2, header_bottom_y + bottom_line_offset, "CODE")
    c.drawCentredString((col_x[3] + col_x[4]) / 2, header_middle_y, "QTY")
    c.drawCentredString((col_x[4] + col_x[5]) / 2, header_top_y - top_line_offset, "UNIT")
    c.drawCentredString((col_x[4] + col_x[5]) / 2, header_bottom_y + bottom_line_offset, "RATE")
    c.drawCentredString((col_x[5] + col_x[6]) / 2, header_top_y - top_line_offset, "TAXABLE")
    c.drawCentredString((col_x[5] + col_x[6]) / 2, header_bottom_y + bottom_line_offset, "VALUE")
    c.drawCentredString((col_x[6] + col_x[7]) / 2, header_top_y - top_line_offset, "CGST")
    c.drawCentredString((col_x[7] + col_x[8]) / 2, header_top_y - top_line_offset, "SGST")
    c.drawCentredString((col_x[8] + col_x[9]) / 2, header_top_y - top_line_offset, "IGST")

    c.setFont("Helvetica-Bold", 6)
    for i in [6, 7, 8]:
        left = col_x[i]
        mid = left + (column_widths[i] / 2)
        right = col_x[i + 1]
        c.drawCentredString((left + mid) / 2, header_bottom_y + bottom_line_offset, "RATE OF %")
        c.drawCentredString((mid + right) / 2, header_bottom_y + bottom_line_offset, "AMOUNT")

    c.setFillColor(black)
    items = items or []
    total_taxable = 0.0
    total_cgst_amt = 0.0
    total_sgst_amt = 0.0
    total_igst_amt = 0.0
    current_y = y - header_height - 12

    for i in range(total_data_rows):
        if i < len(items):
            item = items[i]
            desc = (item.get("item_desc") or "").strip()
            qty = safe_float(item.get("item_qty"))
            rate = safe_float(item.get("item_rate"))
            cgst = safe_float(item.get("item_cgst"))
            sgst = safe_float(item.get("item_sgst"))
            igst = safe_float(item.get("item_igst"))

            taxable = qty * rate
            cgst_amt = taxable * cgst / 100
            sgst_amt = taxable * sgst / 100
            igst_amt = taxable * igst / 100

            total_taxable += taxable
            total_cgst_amt += cgst_amt
            total_sgst_amt += sgst_amt
            total_igst_amt += igst_amt

            # Wrap description text
            desc_lines = wrap_text(desc, "Helvetica-Oblique", 6.8, column_widths[1] - 4)
            required_height = max(row_height, len(desc_lines) * 8)  # Adjust row height

            # Draw SR. NO.
            c.setFont("Helvetica", 7)
            c.drawRightString(col_x[0] + column_widths[0] - 2, current_y, str(i + 1))

            # Draw DESCRIPTION
            c.setFont("Helvetica-Oblique", 6.8)
            text_obj = c.beginText()
            text_obj.setTextOrigin(col_x[1] + 2, current_y)
            for line in desc_lines:
                text_obj.textLine(line)
            c.drawText(text_obj)

            # Draw other values
            c.setFont("Helvetica-Oblique", 7)
            c.drawRightString(col_x[2] + column_widths[2] - 2, current_y,
                              format_item_value(item.get("item_hsn", ""), 'hsn'))
            c.drawRightString(col_x[3] + column_widths[3] - 2, current_y, format_item_value(qty, 'qty'))
            c.drawRightString(col_x[4] + column_widths[4] - 2, current_y, format_item_value(rate, 'rate'))
            c.drawRightString(col_x[5] + column_widths[5] - 2, current_y, format_item_value(taxable, 'amount'))
            c.drawRightString(col_x[6] + column_widths[6] / 2 - 2, current_y, format_item_value(cgst, 'percentage'))
            c.drawRightString(col_x[6] + column_widths[6] - 2, current_y, format_item_value(cgst_amt, 'amount'))
            c.drawRightString(col_x[7] + column_widths[7] / 2 - 2, current_y, format_item_value(sgst, 'percentage'))
            c.drawRightString(col_x[7] + column_widths[7] - 2, current_y, format_item_value(sgst_amt, 'amount'))
            c.drawRightString(col_x[8] + column_widths[8] / 2 - 2, current_y, format_item_value(igst, 'percentage'))
            c.drawRightString(col_x[8] + column_widths[8] - 2, current_y, format_item_value(igst_amt, 'amount'))

            # Move down based on wrapped text
            current_y -= required_height
        else:
            # Empty rows
            current_y -= row_height

        # --- TOTAL ROW FIXED AS IS ---
    total_row_top_y = y - header_height - (row_height * total_data_rows)
    total_row_bottom_y = total_row_top_y - row_height
    c.line(x, total_row_top_y, col_x[-1], total_row_top_y)
    label_y = (total_row_top_y + total_row_bottom_y) / 2 - 2
    c.setFont("Helvetica-Bold", 7)
    c.drawRightString(col_x[4] - 2, label_y, "Total")
    c.drawRightString(col_x[5] + column_widths[5] - 2, label_y, fmt_or_blank(total_taxable))
    c.drawRightString(col_x[6] + column_widths[6] - 2, label_y, fmt_or_blank(total_cgst_amt))
    c.drawRightString(col_x[7] + column_widths[7] - 2, label_y, fmt_or_blank(total_sgst_amt))
    c.drawRightString(col_x[8] + column_widths[8] - 2, label_y, fmt_or_blank(total_igst_amt))

    for i in range(len(col_x)):
        c.line(col_x[i], total_row_top_y, col_x[i], total_row_bottom_y)
    c.line(x, total_row_bottom_y, col_x[-1], total_row_bottom_y)

    return {
        "taxable": total_taxable,
        "cgst_amt": total_cgst_amt,
        "sgst_amt": total_sgst_amt,
        "igst_amt": total_igst_amt
    }


def draw_three_column_box(c, x, y, width, total_taxable, total_cgst_amt, total_sgst_amt, total_igst_amt):
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.utils import simpleSplit

    total_taxable = safe_float(total_taxable)
    total_cgst_amt = safe_float(total_cgst_amt)
    total_sgst_amt = safe_float(total_sgst_amt)
    total_igst_amt = safe_float(total_igst_amt)

    total_after_tax = total_taxable + total_cgst_amt + total_sgst_amt + total_igst_amt

    # --- New Logic: Calculate the rounded total based on your rule. ---
    fractional_part, integer_part = math.modf(total_after_tax)

    if fractional_part > 0.50:
        rounded_total = int(integer_part) + 1
    else:
        rounded_total = int(integer_part)
    # --- End of new logic ---

    height = 6 * 12
    row_height = height / 6
    col_width = width / 3
    right = x + width
    bottom_y = y - height
    line_y = [y - i * row_height for i in range(7)]

    box3_left = x + 2 * col_width
    for ly in line_y:
        c.line(box3_left, ly, right, ly)

    for i in range(4):
        c.line(x + i * col_width, y, x + i * col_width, bottom_y)

    c.line(x, bottom_y, x + col_width, bottom_y)
    c.line(x + col_width, bottom_y, x + 2 * col_width, bottom_y)

    c.setFont("Helvetica-Bold", 7)
    c.setFillColor(HexColor("#d14000"))
    c.drawCentredString(x + col_width / 2, line_y[1] + 2, "Bank Details:")
    c.setFillColor(black)
    c.setFont("Helvetica-Bold", 6.8)
    bank_lines = [
        "Bank Name- Axis Bank Ltd.",
        "Branch Name- Bund Garden Branch, Pune.411001",
        "Account No. 911020065043421",
        "Account Type- Current , IFSC Code- UTIB0000073"
    ]
    for i, line in enumerate(bank_lines):
        c.drawCentredString(x + col_width / 2, line_y[i + 2] + (row_height / 2) - 3, line)

    c.setFont("Helvetica-Bold", 6.8)
    col2_center = x + 1.5 * col_width
    c.drawCentredString(col2_center, line_y[1] + 2, "Total Invoice Value (In Words):")

    # Use the new rounded total value for the num2words conversion
    if rounded_total >= 0:
        amount_words_str = ""
        try:
            # Convert the rounded_total to words
            rupees_words = num2words(rounded_total, lang='en_IN').title()

            # Construct the final string with "Rupees Only"
            amount_words_str = f"{rupees_words} Rupees Only."

        except Exception as e:
            amount_words_str = "Error in converting amount to words."
            print(f"Error converting number to words: {e}")

        # Remove commas and hyphens from the string
        amount_words_str = amount_words_str.replace(",", "").replace("-", " ")

        # Use the existing wrapping and drawing logic
        wrapped_lines = simpleSplit(amount_words_str, "Helvetica-Bold", 6.8, col_width - 10)
        text_start_y = line_y[2] + (row_height / 2) - 3

        for i, line in enumerate(wrapped_lines):
            if i >= 3:
                break
            line_y_pos = text_start_y - (i * row_height)
            c.drawCentredString(col2_center, line_y_pos, line)

    value_x = box3_left + col_width - 4
    separator_x = value_x - 40
    c.setLineWidth(0.5)
    c.line(separator_x, line_y[6], separator_x, line_y[0])

    c.setFont("Helvetica", 6.8)
    c.drawRightString(separator_x - 4, line_y[1] + 2, "Total Amount Before Tax :")
    c.drawRightString(value_x, line_y[1] + 2, f"{total_taxable:.2f}")
    c.drawRightString(separator_x - 4, line_y[2] + 2, "Add. CGST :")
    c.drawRightString(value_x, line_y[2] + 2, f"{total_cgst_amt:.2f}")
    c.drawRightString(separator_x - 4, line_y[3] + 2, "Add. SGST :")
    c.drawRightString(value_x, line_y[3] + 2, f"{total_sgst_amt:.2f}")
    c.drawRightString(separator_x - 4, line_y[4] + 2, "Add. IGST :")
    c.drawRightString(value_x, line_y[4] + 2, f"{total_igst_amt:.2f}")

    c.setFont("Helvetica-Bold", 6.8)
    c.drawRightString(separator_x - 4, line_y[5] + 2, "Total Amount After Tax :")
    c.drawRightString(value_x, line_y[5] + 2, f"{rounded_total:.2f}")


def draw_terms_and_conditions(c, left_x, footer_y, footer_height):
    c.setFont("Helvetica-BoldOblique", 8)
    c.setFillColor(HexColor("#D44826"))
    heading_text = "Terms & Conditions:"
    heading_x = left_x + 5
    heading_y = footer_y + footer_height - 10
    c.drawString(heading_x, heading_y, heading_text)
    c.line(heading_x, heading_y - 2, heading_x + stringWidth(heading_text, "Helvetica-BoldOblique", 8), heading_y - 2)
    c.setFont("Helvetica-Oblique", 7)
    c.setFillColor("black")
    terms = [
        "1. Goods once sold will not be returned.",
        "2. Make all cheques payable to Pions Technologies Pvt. Ltd.",
        "3. All Disputes are subjected to Pune Jurisdiction."
    ]
    for i, line in enumerate(terms):
        c.drawString(heading_x + 5, heading_y - 15 - i * 10, line)


# === PDF Generation Functions ===
def generate_invoice_form(label_text, temp_filename, items=None, invoice_data=None):
    if isinstance(temp_filename, (str, bytes, os.PathLike)):
        temp_filename = os.path.abspath(temp_filename)
        os.makedirs(os.path.dirname(temp_filename), exist_ok=True)
        c = canvas.Canvas(temp_filename, pagesize=A4)
    else:
        c = canvas.Canvas(temp_filename, pagesize=A4)

    width, height = A4
    top_margin = 5 * mm
    side_margin = 5 * mm
    bottom_margin = 3 * mm
    usable_width = width - 2 * side_margin
    row_height = 11

    # --- Draw main border ---
    c.setLineWidth(1.4)
    c.rect(side_margin, bottom_margin, usable_width, height - top_margin - bottom_margin)

    # --- Header ---
    header_height = 75
    header_y = height - top_margin - header_height
    c.setLineWidth(1.1)
    c.rect(side_margin, header_y, usable_width, header_height)
    text_y = height - top_margin - 15
    offset = -20
    c.setFont("Helvetica-BoldOblique", 12)
    c.drawCentredString((width / 2) + offset, text_y, "Pions Technologies Pvt. Ltd.")
    c.setFont("Helvetica-BoldOblique", 7)
    c.drawCentredString((width / 2) + offset, text_y - 10,
                        "Office No.301, Rainbow Plaza, Near Hotel Shivar Garden, Rahatni, Pune - 411017")
    c.drawString(135, text_y - 20, "Telephone No. 9922799835")
    c.drawString(275, text_y - 20, "Mail Id: response@pionstechnologies.com")
    c.setFont("Helvetica-BoldOblique", 8)
    c.setFillColor(HexColor("#D44826"))
    c.drawString(125, text_y - 30, "GSTIN Code: 27AAECP2263K1Z9")
    c.drawString(335, text_y - 30, "PAN No.: AAECP2263K")
    c.setFillColor("black")
    c.setFont("Helvetica-BoldOblique", 9)
    c.drawCentredString((width / 2) + offset, text_y - 52, "PERFORMA INVOICE")

    # --- Logo ---
    logo_path = "assets/logo.png"
    logo_width = 120
    logo_height = 65
    logo_x = width - side_margin - logo_width - 5
    logo_y = height - top_margin - 70
    if os.path.exists(logo_path):
        logo = ImageReader(logo_path)
        c.drawImage(logo, logo_x, logo_y, width=logo_width, height=logo_height, preserveAspectRatio=True, mask='auto')
        c.setFont("Helvetica-Oblique", 7)
        c.drawCentredString(logo_x + logo_width / 2, logo_y - 0, label_text)

    # --- Info boxes, address boxes, items table, totals, footer ---
    info_box_top_y = height - top_margin - header_height
    draw_invoice_info_box(c, side_margin, info_box_top_y, usable_width, invoice_data=invoice_data)
    info_box_height = 11 * 5
    address_box_top_y = info_box_top_y - (info_box_height + 10)
    left_address = invoice_data.get("invoiced_to_address", "")
    right_address = invoice_data.get("consigned_to_address", "")
    address_box_bottom_y = draw_address_box(
        c, side_margin, address_box_top_y, usable_width, row_height, 0,
        left_address, right_address
    )
    gst_box_bottom_y = draw_state_gstin_box(
        c, side_margin, address_box_bottom_y, usable_width, row_height,
        left_state=invoice_data.get("invoiced_state", ""),
        left_state_code=invoice_data.get("invoiced_state_code", ""),
        left_gstin=invoice_data.get("invoiced_gstin", ""),
        right_state=invoice_data.get("consigned_state", ""),
        right_state_code=invoice_data.get("consigned_state_code", ""),
        right_gstin=invoice_data.get("consigned_gstin", "")
    )
    vendor_po_bottom_y = draw_vendor_po_box(
        c, side_margin, gst_box_bottom_y - 5, usable_width, row_height,
        invoice_data=invoice_data
    )
    footer_height = 85
    footer_y = bottom_margin
    table_top_y = vendor_po_bottom_y - 10
    totals = draw_invoice_item_table(
        c,
        x=side_margin,
        y=table_top_y,
        width=usable_width,
        header_height=24,
        row_height=14,
        items=items
    )
    totals_box_height = 65
    gap_above_footer = 22
    totals_box_y = footer_y + footer_height + gap_above_footer + totals_box_height
    draw_three_column_box(
        c,
        x=side_margin,
        y=totals_box_y,
        width=usable_width,
        total_taxable=totals["taxable"],
        total_cgst_amt=totals["cgst_amt"],
        total_sgst_amt=totals["sgst_amt"],
        total_igst_amt=totals["igst_amt"]
    )
    c.setLineWidth(1.1)
    c.rect(side_margin, footer_y, usable_width, footer_height)
    center_col_width = 110
    side_col_width = (usable_width - center_col_width) / 2
    left_x = side_margin
    center_x = left_x + side_col_width
    right_x = center_x + center_col_width
    c.line(center_x, footer_y, center_x, footer_y + footer_height)
    c.line(right_x, footer_y, right_x, footer_y + footer_height)
    draw_terms_and_conditions(c, left_x, footer_y, footer_height)
    c.setFillColor(HexColor("#D44826"))
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(center_x + center_col_width / 2, footer_y + footer_height - 10, "Pre-authentication")
    right_center_x = right_x + side_col_width / 2
    c.setFillColor("black")
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(right_center_x, footer_y + footer_height - 10, "For Pions Technologies Pvt. Ltd.")
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(HexColor("#D44826"))
    c.drawCentredString(right_center_x, footer_y + 5, "Authorised Signatory")
    c.save()




def generate_and_merge_all(output_file=None, items=None, invoice_data=None):
    labels = [
        "Original For Recipient",
        "Duplicate For Transport",
        "Triplicate For Supplier",
        "Extra"
    ]
    os.makedirs(TEMP_FOLDER, exist_ok=True)
    merger = PdfMerger()
    temp_files = []

    for label in labels:
        safe_label = label.lower().replace(" ", "_")
        temp_filename = os.path.join(TEMP_FOLDER, f"{safe_label}.pdf")
        try:
            os.makedirs(os.path.dirname(temp_filename), exist_ok=True)
            generate_invoice_form(label, temp_filename, items=items, invoice_data=invoice_data)
            if os.path.exists(temp_filename):
                merger.append(temp_filename)
                temp_files.append(temp_filename)
        except Exception as e:
            pass

    if output_file is None:
        output_buffer = io.BytesIO()
        merger.write(output_buffer)
        merger.close()
        output_buffer.seek(0)
        for f in temp_files:
            try:
                os.remove(f)
            except Exception as e:
                pass
        try:
            os.rmdir(TEMP_FOLDER)
        except OSError:
            pass
        return output_buffer.getvalue()

    if temp_files:
        try:
            merger.write(output_file)
        finally:
            merger.close()
        for f in temp_files:
            try:
                os.remove(f)
            except Exception as e:
                pass
        try:
            os.rmdir(TEMP_FOLDER)
        except OSError:
            pass
        return output_file


# === Routes ===
@app.route('/')
def index():
    return render_template('index.html')


@app.route("/generate", methods=["POST"])
def generate():
    data = request.form
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:

                # --- Generate safe invoice number ---
                def get_next_invoice_no(cur):
                    current_year = datetime.now().year
                    next_year = current_year + 1
                    fin_year = f"{current_year}-{str(next_year)[-2:]}"  # e.g., 2025-26
                    cur.execute("LOCK TABLE invoices IN EXCLUSIVE MODE")
                    cur.execute("""
                        SELECT invoice_no FROM invoices
                        WHERE invoice_no LIKE %s
                        ORDER BY invoice_no DESC LIMIT 1
                    """, (f"PTPL/{fin_year}/%",))
                    row = cur.fetchone()
                    if row:
                        last_no = int(row[0].split('/')[-1])
                        next_no = f"{last_no + 1:03d}"
                    else:
                        next_no = "001"
                    return f"PTPL/{fin_year}/{next_no}"

                invoice_no = get_next_invoice_no(cur)

                # --- Insert invoice data ---
                cur.execute('''
                    INSERT INTO invoices (
                        invoice_no, invoice_date, state, state_code, delivery_challan_no,
                        delivery_challan_date, transport_mode, vehicle_no, date_of_supply,
                        place_of_supply, insurance_policy_no, insurance_policy_date,
                        vendor_code, po_no, po_date, invoiced_to_address, invoiced_state,
                        invoiced_state_code, invoiced_gstin, consigned_to_address,
                        consigned_state, consigned_state_code, consigned_gstin
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id
                ''', (
                    invoice_no, data.get('invoice_date'), data.get('state'), data.get('state_code'),
                    data.get('delivery_challan_no'), data.get('delivery_challan_date'), data.get('transport_mode'),
                    data.get('vehicle_no'), data.get('date_of_supply'), data.get('place_of_supply'),
                    data.get('insurance_policy_no'), data.get('insurance_policy_date'), data.get('vendor_code'),
                    data.get('po_no'), data.get('po_date'), data.get('invoiced_to_address'), data.get('invoiced_state'),
                    data.get('invoiced_state_code'), data.get('invoiced_gstin'), data.get('consigned_to_address'),
                    data.get('consigned_state'), data.get('consigned_state_code'), data.get('consigned_gstin')
                ))
                invoice_id = cur.fetchone()[0]

                # --- Insert invoice items ---
                items_for_pdf = []
                item_fields = ["item_desc[]", "item_hsn[]", "item_qty[]", "item_rate[]", "item_cgst[]", "item_sgst[]", "item_igst[]"]
                items_lists = [data.getlist(f) for f in item_fields]
                for i in range(len(items_lists[0])):
                    desc = items_lists[0][i]
                    if desc.strip():
                        item = {
                            "item_desc": desc,
                            "item_hsn": items_lists[1][i],
                            "item_qty": safe_float(items_lists[2][i]),
                            "item_rate": safe_float(items_lists[3][i]),
                            "item_cgst": safe_float(items_lists[4][i]),
                            "item_sgst": safe_float(items_lists[5][i]),
                            "item_igst": safe_float(items_lists[6][i])
                        }
                        items_for_pdf.append(item)
                        cur.execute('''
                            INSERT INTO invoice_items (
                                invoice_id, item_desc, item_hsn, item_qty, item_rate,
                                item_cgst, item_sgst, item_igst
                            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                        ''', (
                            invoice_id, item["item_desc"], item["item_hsn"], item["item_qty"], item["item_rate"],
                            item["item_cgst"], item["item_sgst"], item["item_igst"]
                        ))

                conn.commit()

        # --- Generate PDF ---
        pdf_bytes = generate_and_merge_all(
            output_file=None,
            items=items_for_pdf,
            invoice_data={**data, "invoice_no": invoice_no}
        )

        return send_file(
            io.BytesIO(pdf_bytes),
            as_attachment=True,
            download_name=f"{invoice_no}.pdf",
            mimetype="application/pdf"
        )

    except Exception as e:
        logger.exception("Error generating invoice")
        return f"Error generating invoice: {str(e)}", 500

@app.route("/reprint_page")
def reprint_page():
    return render_template("reprint.html")


@app.route('/reprint', methods=['GET'])
def reprint():
    invoice_no = request.args.get('invoice_no')
    if not invoice_no:
        return render_template('reprint.html', error="Please enter an invoice number.")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get invoice
                cur.execute("SELECT * FROM invoices WHERE invoice_no = %s", (invoice_no,))
                row = cur.fetchone()
                if not row:
                    return render_template('reprint.html', error="Invoice not found in database.")

                columns = [desc[0] for desc in cur.description]
                invoice_data = dict(zip(columns, row))
                invoice_id = invoice_data['id']

                # Get items
                cur.execute("SELECT * FROM invoice_items WHERE invoice_id = %s", (invoice_id,))
                item_rows = cur.fetchall()
                item_columns = [desc[0] for desc in cur.description]
                items = [dict(zip(item_columns, r)) for r in item_rows]

        # Add items into invoice_data
        invoice_data["items"] = items

        # Generate PDF (same function as /generate)
        # In reprint()
        pdf_bytes = generate_and_merge_all(
            output_file=None,
            items=invoice_data["items"],
            invoice_data=invoice_data
        )

        return send_file(
            io.BytesIO(pdf_bytes),
            as_attachment=True,
            download_name=f"{invoice_no.replace('/', '_')}.pdf",
            mimetype="application/pdf"
        )

    except Exception as e:
        return render_template('reprint.html', error=f"Error generating invoice: {str(e)}")



# === App Startup ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

