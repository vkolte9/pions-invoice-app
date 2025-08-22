# === Performa Invoice PDF Generator for Web App ===

from datetime import datetime
import os
import io
import json
import math # Import math for ceil and floor functions

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.lib.colors import HexColor, black
from reportlab.pdfbase.pdfmetrics import stringWidth
from PyPDF2 import PdfMerger
from num2words import num2words

# ---------- Config ----------
TEMP_FOLDER = "temp_invoices"
DATA_FILE = "last_invoice_data.json"
os.makedirs(TEMP_FOLDER, exist_ok=True)


# ---------- Helpers ----------
# Moved safe_float outside the function for broader usability if needed,
# and consistency.
def safe_float(val):
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0



def fmt_or_blank(val: float) -> str:
    """Return formatted value if non-zero, else blank."""
    return f"{val:.2f}" if val != 0 else ""


# ---------- Persist form data (for future GUI) ----------
def save_form_data(field_dict):
    try:
        data = {key: entry.get() for key, entry in field_dict.items()}
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)
        print("✅ Form data saved.")
    except Exception as e:
        print(f"❌ Error saving form data: {e}")


def load_form_data(field_dict):
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
            for key, entry in field_dict.items():
                if key in data:
                    entry.delete(0, 'end')
                    entry.insert(0, data[key])
            print("🔁 Form data loaded.")
        except Exception as e:
            print(f"❌ Error loading form data: {e}")


# ---------- Layout blocks ----------
def draw_invoice_info_box(c, x, y, width, row_height=11, invoice_data=None):
    col_width = width / 2
    info_box_height = row_height * 5

    c.setLineWidth(1)
    c.rect(x, y - info_box_height, width, info_box_height)
    c.line(x + col_width, y, x + col_width, y - info_box_height)

    label_x = x + 5
    value_x = x + col_width / 2 + 5
    base_y = y - 9

    # Use data from invoice_data dictionary
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


# (The rest of the functions `draw_invoice_item_table`, `draw_three_column_box`,
# `draw_terms_and_conditions` are unchanged. )
def draw_invoice_item_table(c, x, y, width, header_height=24, row_height=14, items=None):
    """
    Draws the item table. Returns totals dict:
    {'taxable': float, 'cgst_amt': float, 'sgst_amt': float, 'igst_amt': float}
    """
    orange = HexColor("#d14000")

    # Helper function for formatting numbers in table cells
    def format_item_value(value, value_type): # value_type can be 'qty', 'hsn', 'rate', 'percentage', 'amount'
        num = safe_float(value)

        if value_type == 'qty' or value_type == 'percentage':
            # Display '0' for zero, otherwise integer part
            return str(int(num)) if num != 0.0 else "0"
        elif value_type == 'rate':
            # Display '0' for zero, otherwise two decimal places
            return f"{num:.2f}" if num != 0.0 else "0"
        elif value_type == 'amount':
            # Display '0.00' for zero, otherwise two decimal places
            return f"{num:.2f}" if num != 0.0 else "0.00"
        else: # for hsn (text) or unexpected types, just return string representation
            return str(value if value is not None else "")

    # Helper function for formatting totals in the last row
    def fmt_or_blank(value):
        num = safe_float(value)
        return f"{num:.2f}" # Always .00 for total amounts

    # Column widths (these are from your original PDF code, assumed to be final for PDF layout)
    column_widths = [
        7 * mm,  # NO.
        51 * mm,  # DESCRIPTION
        15 * mm,  # HSN/SAC
        10 * mm,  # QTY
        18 * mm,  # UNIT RATE
        18 * mm,  # TAXABLE VALUE
        27 * mm,  # CGST
        27 * mm,  # SGST
        27 * mm  # IGST
    ]
    col_x = [x]
    for w in column_widths:
        col_x.append(col_x[-1] + w)

    total_data_rows = 25 # Number of rows available for items
    table_height = header_height + (row_height * total_data_rows)

    header_top_y = y
    header_bottom_y = y - header_height
    header_middle_y = y - (header_height / 2)
    top_line_offset = header_height * 0.3
    bottom_line_offset = header_height * 0.2

    # Grid drawing
    for i in range(len(col_x)):
        c.line(col_x[i], y, col_x[i], y - table_height)
    for i in [6, 7, 8]: # Vertical lines for CGST, SGST, IGST subdivisions
        mid = col_x[i] + (column_widths[i] / 2)
        c.line(col_x[i], header_middle_y, col_x[i + 1], header_middle_y) # Horizontal line across Rate/Amount
        c.line(mid, header_middle_y, mid, y - table_height) # Vertical line down the middle of Rate/Amount
    c.line(x, y, col_x[-1], y) # Top horizontal line
    c.line(x, y - header_height, col_x[-1], y - header_height) # Header bottom horizontal line

    # Header labels
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
    for i in [6, 7, 8]: # Sub-headers for CGST, SGST, IGST columns
        left = col_x[i]
        mid = left + (column_widths[i] / 2)
        right = col_x[i + 1]
        c.drawCentredString((left + mid) / 2, header_bottom_y + bottom_line_offset, "RATE OF %")
        c.drawCentredString((mid + right) / 2, header_bottom_y + bottom_line_offset, "AMOUNT")

    # Data
    c.setFillColor(black)

    # Ensure items is an iterable, even if empty
    items = items or []

    total_taxable = 0.0
    total_cgst_amt = 0.0
    total_sgst_amt = 0.0
    total_igst_amt = 0.0

    data_start_y = y - header_height - 12 # Starting Y position for the first data row

    # Draw data rows
    for i in range(total_data_rows):
        row_y = data_start_y - (i * row_height)
        if i < len(items):
            item = items[i]
            desc = (item.get("desc") or "").strip()
            qty = safe_float(item.get("qty"))
            rate = safe_float(item.get("rate"))
            cgst = safe_float(item.get("cgst"))
            sgst = safe_float(item.get("sgst"))
            igst = safe_float(item.get("igst"))

            taxable = qty * rate
            cgst_amt = taxable * cgst / 100
            sgst_amt = taxable * sgst / 100
            igst_amt = taxable * igst / 100

            total_taxable += taxable
            total_cgst_amt += cgst_amt
            total_sgst_amt += sgst_amt
            total_igst_amt += igst_amt

            # SR No
            c.setFont("Helvetica", 7)
            c.drawRightString(col_x[0] + column_widths[0] - 2, row_y, str(i + 1))

            # Description (supports multiline)
            c.setFont("Helvetica-Oblique", 6.8)
            text_obj = c.beginText()
            text_obj.setTextOrigin(col_x[1] + 2, row_y)
            for line in desc.split("\n"):
                text_obj.textLine(line)
            c.drawText(text_obj)

            # Other fields with new formatting
            c.setFont("Helvetica-Oblique", 7)
            c.drawRightString(col_x[2] + column_widths[2] - 2, row_y, format_item_value(item.get("hsn", ""), 'hsn'))
            c.drawRightString(col_x[3] + column_widths[3] - 2, row_y, format_item_value(qty, 'qty'))
            c.drawRightString(col_x[4] + column_widths[4] - 2, row_y, format_item_value(rate, 'rate'))
            c.drawRightString(col_x[5] + column_widths[5] - 2, row_y, format_item_value(taxable, 'amount'))

            # CGST Rate and Amount
            c.drawRightString(col_x[6] + column_widths[6] / 2 - 2, row_y, format_item_value(cgst, 'percentage'))
            c.drawRightString(col_x[6] + column_widths[6] - 2, row_y, format_item_value(cgst_amt, 'amount'))

            # SGST Rate and Amount
            c.drawRightString(col_x[7] + column_widths[7] / 2 - 2, row_y, format_item_value(sgst, 'percentage'))
            c.drawRightString(col_x[7] + column_widths[7] - 2, row_y, format_item_value(sgst_amt, 'amount'))

            # IGST Rate and Amount
            c.drawRightString(col_x[8] + column_widths[8] / 2 - 2, row_y, format_item_value(igst, 'percentage'))
            c.drawRightString(col_x[8] + column_widths[8] - 2, row_y, format_item_value(igst_amt, 'amount'))

    # Totals row (below data rows)
    total_row_top_y = y - header_height - (row_height * total_data_rows)
    total_row_bottom_y = total_row_top_y - row_height

    c.line(x, total_row_top_y, col_x[-1], total_row_top_y) # Top line of totals row
    label_y = (total_row_top_y + total_row_bottom_y) / 2 - 2 # Vertical center for text in totals row
    c.setFont("Helvetica-Bold", 7)
    c.drawRightString(col_x[4] - 2, label_y, "Total") # "Total" label

    # Draw formatted total amounts
    c.drawRightString(col_x[5] + column_widths[5] - 2, label_y, fmt_or_blank(total_taxable))
    c.drawRightString(col_x[6] + column_widths[6] - 2, label_y, fmt_or_blank(total_cgst_amt))
    c.drawRightString(col_x[7] + column_widths[7] - 2, label_y, fmt_or_blank(total_sgst_amt))
    c.drawRightString(col_x[8] + column_widths[8] - 2, label_y, fmt_or_blank(total_igst_amt))

    # Draw vertical lines for the totals row to align with columns above
    for i in range(len(col_x)):
        c.line(col_x[i], total_row_top_y, col_x[i], total_row_bottom_y)
    c.line(x, total_row_bottom_y, col_x[-1], total_row_bottom_y) # Bottom horizontal line of totals row

    return {
        "taxable": total_taxable,
        "cgst_amt": total_cgst_amt,
        "sgst_amt": total_sgst_amt,
        "igst_amt": total_igst_amt
    }


def draw_three_column_box(c, x, y, width, total_taxable, total_cgst_amt, total_sgst_amt, total_igst_amt):
    """
    Draws the three-column section at the bottom, including bank details, amount in words, and final totals.
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.utils import simpleSplit  # Assuming simpleSplit is available

    # Safe numbers
    total_taxable = safe_float(total_taxable)
    total_cgst_amt = safe_float(total_cgst_amt)
    total_sgst_amt = safe_float(total_sgst_amt)
    total_igst_amt = safe_float(total_igst_amt)

    height = 6 * 12  # 6 rows of 12pt
    row_height = height / 6
    col_width = width / 3
    right = x + width
    bottom_y = y - height
    line_y = [y - i * row_height for i in range(7)]

    # Column 3 grid (Totals section)
    box3_left = x + 2 * col_width
    for ly in line_y:
        c.line(box3_left, ly, right, ly)  # Horizontal lines for column 3

    # Vertical lines for the entire three-column box
    for i in range(4):  # 0, 1, 2, 3 correspond to x, x+col_width, x+2*col_width, x+width
        c.line(x + i * col_width, y, x + i * col_width, bottom_y)

    # Bottom lines for column 1 and 2
    c.line(x, bottom_y, x + col_width, bottom_y)
    c.line(x + col_width, bottom_y, x + 2 * col_width, bottom_y)

    # Column 1: Bank Details
    c.setFont("Helvetica-Bold", 7)
    c.setFillColor(HexColor("#d14000"))  # Using HexColor for consistency
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
        # Adjust Y position based on line_y offsets to center text vertically within its row
        # This assumes line_y[i+2] corresponds to the top of the text area for the first line.
        # A more robust solution might calculate the exact text baseline.
        # For simple strings, this should be adequate.
        c.drawCentredString(x + col_width / 2, line_y[i + 2] + (row_height / 2) - 3, line)

    # Column 2: Amount in Words (Conditional "Rupees Only" vs "Rupees and Paise Only")
    total_after_tax = total_taxable + total_cgst_amt + total_sgst_amt + total_igst_amt
    c.setFont("Helvetica-Bold", 6.8)
    col2_center = x + 1.5 * col_width
    c.drawCentredString(col2_center, line_y[1] + 2, "Total Invoice Value (In Words):")  # Moved up to line_y[1] + 2

    if total_after_tax >= 0:  # Handle 0 case too, to say "Zero Rupees Only"
        rupees_part = int(math.floor(total_after_tax))
        paise_part = int(round((total_after_tax - rupees_part) * 100))

        amount_words_str = ""
        try:
            rupees_words = num2words(rupees_part, lang='en_IN').title()
            amount_words_str = f"{rupees_words} Rupees"

            if paise_part > 0:
                paise_words = num2words(paise_part, lang='en_IN').title()
                amount_words_str += f" And {paise_words} Paise"

            amount_words_str += " Only."

        except Exception as e:
            amount_words_str = "Error in converting amount to words."
            print(f"Error converting number to words: {e}")

        # Clean up commas and hyphens if num2words adds them
        amount_words_str = amount_words_str.replace(",", "").replace("-", " ")

        # Wrapping logic for long strings
        # `col_width - 10` for padding on left/right
        wrapped_lines = simpleSplit(amount_words_str, "Helvetica-Bold", 6.8, col_width - 10)

        # Start drawing lines below the "Total Invoice Value (In Words):" header.
        # line_y[2] is the top of the second row, so line_y[2] + 2 is a good starting point for content.
        # Adjusting this based on the header's position
        text_start_y = line_y[2] + (row_height / 2) - 3  # Adjusted to start closer to the header

        for i, line in enumerate(wrapped_lines):
            if i >= 3:  # Limit to 3 lines to prevent overflow
                break
            line_y_pos = text_start_y - (i * row_height)
            c.drawCentredString(col2_center, line_y_pos, line)

    # Column 3: Final Totals
    value_x = box3_left + col_width - 4
    separator_x = value_x - 40  # Position of the line separating labels from values

    c.setLineWidth(0.5)
    c.line(separator_x, line_y[6], separator_x, line_y[0])  # Vertical line for totals section

    c.setFont("Helvetica", 6.8)
    # Total Amount Before Tax
    c.drawRightString(separator_x - 4, line_y[1] + 2, "Total Amount Before Tax :")
    c.drawRightString(value_x, line_y[1] + 2, f"{total_taxable:.2f}")

    # Add. CGST
    c.drawRightString(separator_x - 4, line_y[2] + 2, "Add. CGST :")
    c.drawRightString(value_x, line_y[2] + 2, f"{total_cgst_amt:.2f}")

    # Add. SGST
    c.drawRightString(separator_x - 4, line_y[3] + 2, "Add. SGST :")
    c.drawRightString(value_x, line_y[3] + 2, f"{total_sgst_amt:.2f}")

    # Add. IGST
    c.drawRightString(separator_x - 4, line_y[4] + 2, "Add. IGST :")
    c.drawRightString(value_x, line_y[4] + 2, f"{total_igst_amt:.2f}")

    c.setFont("Helvetica-Bold", 6.8)
    # Total Amount After Tax
    c.drawRightString(separator_x - 4, line_y[5] + 2, "Total Amount After Tax :")
    c.drawRightString(value_x, line_y[5] + 2, f"{total_after_tax:.2f}")  # Format to 2 decimal places

    # Optional: Draw a vertical line for the signature area if needed
    # c.line(x + 2 * col_width + (col_width / 2), y, x + 2 * col_width + (col_width / 2), bottom_y) # Example


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


# ---------- Page generator ----------
def generate_invoice_form(label_text, temp_filename, items=None, invoice_data=None):
    # Check if temp_filename is a file path (str/Path) or BytesIO
    if isinstance(temp_filename, (str, bytes, os.PathLike)):
        temp_filename = os.path.abspath(temp_filename)
        output_dir = os.path.dirname(temp_filename)
        os.makedirs(output_dir, exist_ok=True)
        c = canvas.Canvas(temp_filename, pagesize=A4)
    else:
        # If temp_filename is BytesIO
        c = canvas.Canvas(temp_filename, pagesize=A4)

    width, height = A4
    top_margin = 5 * mm
    side_margin = 5 * mm
    bottom_margin = 3 * mm
    usable_width = width - 2 * side_margin
    row_height = 11

    # Outer border
    c.setLineWidth(1.4)
    c.rect(side_margin, bottom_margin, usable_width, height - top_margin - bottom_margin)

    # Header
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

    # Logo + copy label
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

    # Info + address + GST + PO
    info_box_top_y = height - top_margin - header_height
    draw_invoice_info_box(c, side_margin, info_box_top_y, usable_width, invoice_data=invoice_data)

    # --- FIX: DEFINE address_box_top_y before use ---
    info_box_height = 11 * 5
    address_box_top_y = info_box_top_y - (info_box_height + 10)
    # --- END FIX ---

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

    # Footer area geometry
    footer_height = 85
    footer_y = bottom_margin

    # Table
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

    # Totals box
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

    # Footer
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

    # Draw footer text
    c.setFont("Helvetica-Oblique", 6)
    c.setFillColor(black)
    footer_text = "THIS IS SYSTEM GENERATED DOCUMENT"
    text_width = c.stringWidth(footer_text, "Helvetica-Oblique", 6)

    # Calculate the x-coordinate to center the text
    center_x = (width - text_width) / 2
    # Place the text just below the bottom margin
    y_position = bottom_margin - 5

    c.drawString(center_x, y_position, footer_text)

    # ... (The rest of your drawing logic) ...
    c.save()


# ---------- Final generator function for web apps ----------
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
            print(f"📄 Generating: {temp_filename}")
            os.makedirs(os.path.dirname(temp_filename), exist_ok=True)
            generate_invoice_form(label, temp_filename, items=items, invoice_data=invoice_data)
            if os.path.exists(temp_filename):
                print(f"✅ Successfully wrote: {temp_filename}")
                merger.append(temp_filename)
                temp_files.append(temp_filename)
            else:
                print(f"⚠️ Skipped missing file: {temp_filename}")
        except Exception as e:
            print(f"❌ Error generating {label}: {e}")

    # Use BytesIO if output_file is None (for web app response)
    if output_file is None:
        output_buffer = io.BytesIO()
        merger.write(output_buffer)
        merger.close()
        output_buffer.seek(0)
        # clean temp files
        for f in temp_files:
            try:
                os.remove(f)
            except Exception as e:
                print(f"⚠️ Could not remove {f}: {e}")
        try:
            os.rmdir(TEMP_FOLDER)
        except OSError:
            pass
        return output_buffer.getvalue()

    # Otherwise write to disk as before
    if temp_files:
        try:
            merger.write(output_file)
            print(f"✅ Merged PDF created: {output_file}")
        finally:
            merger.close()
        # clean temp files
        for f in temp_files:
            try:
                os.remove(f)
            except Exception as e:
                print(f"⚠️ Could not remove {f}: {e}")
        try:
            os.rmdir(TEMP_FOLDER)
            print("🧹 Temp folder cleaned up.")
        except OSError:
            print("ℹ️ Temp folder not empty or in use — not removed.")
        return output_file


# === RUN (example) ===
if __name__ == "__main__":
    # Example data for testing
    example_data = {
        "invoice_no": "PI/2025-26/004",
        "invoice_date": datetime.today().strftime("%d/%m/%Y"),
        "state": "Maharashtra",
        "state_code": "27",
        "delivery_challan_no": "DC/123",
        "delivery_challan_date": "17/08/2025",
        "transport_mode": "Road",
        "vehicle_no": "MH12AB1234",
        "date_of_supply": "18/08/2025",
        "place_of_supply": "Pune",
        "insurance_policy_no": "15340021240200000011",
        "insurance_policy_date": "24/10/2024",
        "invoiced_to_address": "Some Company\n123 Main Street\nPune, Maharashtra",
        "consigned_to_address": "Another Company\n456 Oak Avenue\nMumbai, Maharashtra",
        "invoiced_state": "Maharashtra",
        "invoiced_state_code": "27",
        "invoiced_gstin": "27ABCA1234A1Z1",
        "consigned_state": "Maharashtra",
        "consigned_state_code": "27",
        "consigned_gstin": "27DEFG5678B2Z2",
        "vendor_code": "V-001",
        "po_no": "PO-987",
        "po_date": "15/08/2025"
    }

    example_items = [
        {"desc": "Item 1 Description", "hsn": "123456", "qty": "10", "rate": "1500.00", "cgst": "9", "sgst": "9",
         "igst": "0"},
        {"desc": "Item 2 Description", "hsn": "789012", "qty": "5", "rate": "250.00", "cgst": "0", "sgst": "0",
         "igst": "18"}
    ]

    # Example of generating and saving the PDF to disk
    generate_and_merge_all(output_file="final_invoice.pdf", items=example_items, invoice_data=example_data)