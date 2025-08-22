// Helper function to get today's date in DD/MM/YYYY format
function getTodayDateDDMMYYYY() {
    const today = new Date();
    const day = String(today.getDate()).padStart(2, '0');
    const month = String(today.getMonth() + 1).padStart(2, '0'); // Month is 0-indexed
    const year = today.getFullYear();
    return `${day}/${month}/${year}`;
}

// Helper function to convert DD/MM/YYYY string to YYYY-MM-DD string (for Date object parsing)
function convertDDMMYYYYtoYYYYMMDD(ddmmyyyy) {
    if (!ddmmyyyy) return '';
    const parts = ddmmyyyy.split('/');
    if (parts.length === 3) {
        return `${parts[2]}-${parts[1]}-${parts[0]}`;
    }
    return ''; // Return empty string if format is invalid
}

// Helper function to parse DD/MM/YYYY string to Date object
function parseDateFromDisplay(ddmmyyyy) {
    const yyyymmdd = convertDDMMYYYYtoYYYYMMDD(ddmmyyyy);
    if (yyyymmdd) {
        const date = new Date(yyyymmdd);
        // Check if the date is valid (e.g., "31/02/2024" would result in an invalid date)
        if (!isNaN(date.getTime())) {
            return date;
        }
    }
    return null; // Return null for invalid or empty dates
}


// Function to calculate financial year
function getFinancialYear(date) {
    const year = date.getFullYear();
    const month = date.getMonth() + 1; // Month is 0-indexed

    if (month >= 4) { // April to December
        return `${year}-${String(year + 1).slice(2)}`;
    } else { // January to March
        return `${year - 1}-${String(year).slice(2)}`;
    }
}

// Function to generate the next invoice number
function getNextInvoiceNumber() {
    const prefix = "PTPL/";
    const today = new Date();
    const currentFY = getFinancialYear(today);

    let lastInvoiceData = JSON.parse(localStorage.getItem('lastInvoiceData')) || {
        financialYear: '',
        serial: 0,
    };

    let lastFY = lastInvoiceData.financialYear;
    let lastSerial = lastInvoiceData.serial;

    let newSerial;
    if (currentFY !== lastFY) {
        newSerial = 1; // Reset to 001 for new financial year
        // Special case: if it's the very first load ever and it happens to be 2025-26
        // and you want it to start from 080, adjust here.
        if (lastFY === '' && currentFY === '2025-26' && lastSerial === 0) {
             newSerial = 80; // Start at 080 for the specific initial FY if no data found
        }
        lastFY = currentFY;
    } else {
        newSerial = lastSerial + 1;
    }

    // Format serial number to be 3 digits
    const formattedSerial = String(newSerial).padStart(3, '0');
    const newInvoiceNo = `${prefix}${currentFY}/${formattedSerial}`;

    // Store the new data in localStorage
    localStorage.setItem('lastInvoiceData', JSON.stringify({
        financialYear: lastFY,
        serial: newSerial
    }));

    return newInvoiceNo;
}


// Add dynamic item row with calculations
function addItemRow(desc="", hsn="", qty=0, rate=0, cgst=0, sgst=0, igst=0) {
    const tbody = document.querySelector("#items_table tbody");
    const rows = tbody.querySelectorAll("tr");

    // Remove 'Add Item' button from the previously last row, if it exists
    if (rows.length > 0) {
        const lastRowActionCell = rows[rows.length - 1].querySelector('.action-buttons');
        if (lastRowActionCell) {
            const existingAddButton = lastRowActionCell.querySelector('.add-item-btn');
            if (existingAddButton) {
                existingAddButton.remove();
            }
        }
    }

    const row = document.createElement("tr");
    row.innerHTML = `
        <td class="row-number"></td>
        <td><input type="text" name="item_desc[]" value="${desc}"></td>
        <td><input type="text" name="item_hsn[]" value="${hsn}"></td>
        <td><input type="number" step="0.01" name="item_qty[]" value="${qty}" oninput="updateRowTotal(this)"></td>
        <td><input type="number" step="0.01" name="item_rate[]" value="${rate}" oninput="updateRowTotal(this)"></td>
        <td><input type="number" step="0.01" name="item_cgst[]" value="${cgst}" oninput="updateRowTotal(this)"></td>
        <td><input type="number" step="0.01" name="item_sgst[]" value="${sgst}" oninput="updateRowTotal(this)"></td>
        <td><input type="number" step="0.01" name="item_igst[]" value="${igst}" oninput="updateRowTotal(this)"></td>
        <td class="row-total">0.00</td>
        <td class="action-buttons">
            <button type="button" class="add-item-btn" onclick="addItemRow()">Add Item</button>
            <button type="button" class="remove-item-btn" onclick="removeItemRow(this)">Remove</button>
        </td>
    `;
    tbody.appendChild(row);

    updateRowNumbers();
    updateTotals();
}

function removeItemRow(btn) {
    const row = btn.closest("tr");
    const tbody = row.closest("tbody");
    const isLastRow = row === tbody.lastElementChild; // Check if the row being removed is the last one

    row.remove(); // Remove the row

    updateRowNumbers(); // Update row numbers for remaining rows
    updateTotals(); // Recalculate totals

    const remainingRows = tbody.querySelectorAll('tr'); // Get all remaining rows

    // If the removed row was the last one, and there are still rows left,
    // ensure the 'Add Item' button is present on the new last row.
    if (isLastRow && remainingRows.length > 0) {
        const newLastRowActionCell = remainingRows[remainingRows.length - 1].querySelector('.action-buttons');
        if (newLastRowActionCell && !newLastRowActionCell.querySelector('.add-item-btn')) {
            const addButton = document.createElement('button');
            addButton.type = 'button';
            addButton.className = 'add-item-btn';
            addButton.textContent = 'Add Item';
            addButton.onclick = addItemRow;
            newLastRowActionCell.insertBefore(addButton, newLastRowActionCell.firstChild); // Add to the left
        }
    }
    // If all rows are removed, add one default row
    if (remainingRows.length === 0) {
        addItemRow();
    }
}


function updateRowNumbers() {
    const rows = document.querySelectorAll("#items_table tbody tr");
    rows.forEach((r, i) => r.querySelector(".row-number").textContent = i + 1);
}

function updateRowTotal(input) {
    const row = input.closest("tr");
    const qty = parseFloat(row.querySelector('input[name="item_qty[]"]').value) || 0;
    const rate = parseFloat(row.querySelector('input[name="item_rate[]"]').value) || 0;
    const cgst = parseFloat(row.querySelector('input[name="item_cgst[]"]').value) || 0;
    const sgst = parseFloat(row.querySelector('input[name="item_sgst[]"]').value) || 0;
    const igst = parseFloat(row.querySelector('input[name="item_igst[]"]').value) || 0;

    const taxable = qty * rate;
    const total = taxable + (taxable * (cgst + sgst + igst) / 100);
    row.querySelector(".row-total").textContent = total.toFixed(2);

    updateTotals();
}

function updateTotals() {
    let taxable = 0, cgst_total=0, sgst_total=0, igst_total=0;
    document.querySelectorAll("#items_table tbody tr").forEach(row => {
        const q = parseFloat(row.querySelector('input[name="item_qty[]"]').value) || 0;
        const r = parseFloat(row.querySelector('input[name="item_rate[]"]').value) || 0;
        const c = parseFloat(row.querySelector('input[name="item_cgst[]"]').value) || 0;
        const s = parseFloat(row.querySelector('input[name="item_sgst[]"]').value) || 0;
        const i = parseFloat(row.querySelector('input[name="item_igst[]"]').value) || 0;

        const base = q * r;
        taxable += base;
        cgst_total += base * c / 100;
        sgst_total += base * s / 100;
        igst_total += base * i / 100;
    });

    document.getElementById("total_taxable").textContent = taxable.toFixed(2);
    document.getElementById("total_cgst").textContent = cgst_total.toFixed(2);
    document.getElementById("total_sgst").textContent = sgst_total.toFixed(2);
    document.getElementById("total_igst").textContent = igst_total.toFixed(2);
    document.getElementById("total_amount").textContent = (taxable + cgst_total + sgst_total + igst_total).toFixed(2);
}

// Function to handle PDF generation and page refresh
async function generatePdfAndRefresh() {
    const form = document.querySelector('form');
    const formData = new FormData(form);

    // Manually get the checkbox element
    const sameAsInvoicedCheckbox = document.getElementById("same_as_invoiced");

    // Manually get the values from the invoiced fields
    const invoicedToAddress = document.getElementById("invoiced_to_address").value;
    const invoicedState = document.getElementById("invoiced_state").value;
    const invoicedStateCode = document.getElementById("invoiced_state_code").value;
    const invoicedGstin = document.getElementById("invoiced_gstin").value;

    // If the checkbox is checked, manually set the "Consigned To" data
    if (sameAsInvoicedCheckbox.checked) {
        formData.set('consigned_to_address', invoicedToAddress);
        formData.set('consigned_state', invoicedState);
        formData.set('consigned_state_code', invoicedStateCode);
        formData.set('consigned_gstin', invoicedGstin);
    }

    // Check if the consigned address fields are empty despite the checkbox being unchecked
    if (!sameAsInvoicedCheckbox.checked && !document.getElementById("consigned_to_address").value) {
        formData.set('consigned_to_address', '');
    }

    try {
        const response = await fetch(form.action, {
            method: form.method,
            body: formData,
        });

        if (response.ok) {
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/pdf')) {
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                let invoiceNumberForFilename = document.getElementById("invoice_no").value;
                invoiceNumberForFilename = invoiceNumberForFilename.replace(/\//g, '_');
                a.download = `${invoiceNumberForFilename}.pdf`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                console.log("PDF generation request sent successfully and download initiated.");
            } else {
                console.warn("Server response was OK, but not a PDF file. Content-Type:", contentType);
                const textResponse = await response.text();
                alert("PDF generated, but unable to download. Server response: " + textResponse.substring(0, 100) + "...");
            }
        } else {
            console.error("PDF generation failed with status:", response.status);
            const errorText = await response.text();
            alert("Error generating PDF: " + errorText);
        }
    } catch (error) {
        console.error("Error during PDF generation fetch:", error);
        alert("An error occurred while trying to generate the PDF. Please check your network connection.");
    } finally {
        location.reload();
    }
}

// Function to toggle the Consigned To fields based on the checkbox state
function toggleConsignedToFields() {
    const checkbox = document.getElementById("same_as_invoiced");
    const invoicedToAddress = document.getElementById("invoiced_to_address");
    const invoicedState = document.getElementById("invoiced_state");
    const invoicedStateCode = document.getElementById("invoiced_state_code");
    const invoicedGstin = document.getElementById("invoiced_gstin");

    const consignedToAddress = document.getElementById("consigned_to_address");
    const consignedState = document.getElementById("consigned_state");
    const consignedStateCode = document.getElementById("consigned_state_code");
    const consignedGstin = document.getElementById("consigned_gstin");

    if (checkbox.checked) {
        // Copy values from "Invoiced To"
        consignedToAddress.value = invoicedToAddress.value;
        consignedState.value = invoicedState.value;
        consignedStateCode.value = invoicedStateCode.value;
        consignedGstin.value = invoicedGstin.value;

        // Disable and add a class for styling
        consignedToAddress.disabled = true;
        consignedState.disabled = true;
        consignedStateCode.disabled = true;
        consignedGstin.disabled = true;
        consignedToAddress.classList.add("disabled-field");
        consignedState.classList.add("disabled-field");
        consignedStateCode.classList.add("disabled-field");
        consignedGstin.classList.add("disabled-field");
    } else {
        // Clear the fields and re-enable them
        consignedToAddress.value = "";
        consignedState.value = "";
        consignedStateCode.value = "";
        consignedGstin.value = "";

        consignedToAddress.disabled = false;
        consignedState.disabled = false;
        consignedStateCode.disabled = false;
        consignedGstin.disabled = false;
        consignedToAddress.classList.remove("disabled-field");
        consignedState.classList.remove("disabled-field");
        consignedStateCode.classList.remove("disabled-field");
        consignedGstin.classList.remove("disabled-field");
    }
}


// Event listeners and initializations on page load
window.addEventListener("DOMContentLoaded", () => {
    // Add one default empty row for invoice items
    addItemRow();

    const todayDDMMYYYY = getTodayDateDDMMYYYY();

    // 1. Set today's date for Invoice Date
    document.getElementById("invoice_date").value = todayDDMMYYYY;

    // 2. Set default State, State Code, Place of Supply
    document.getElementById("state").value = "Maharashtra";
    document.getElementById("state_code").value = "27";
    document.getElementById("place_of_supply").value = "Pune";

    // 3. Set Insurance Policy No. and Date (fixed unless changed)
    document.getElementById("insurance_policy_no").value = "15340021240200000011";
    document.getElementById("insurance_policy_date").value = "24/10/2024"; // Set in DD/MM/YYYY

    // 4. Conditional Date Auto-fill Logic
    const deliveryChallanNoInput = document.getElementById("delivery_challan_no");
    const deliveryChallanDateInput = document.getElementById("delivery_challan_date");
    deliveryChallanNoInput.addEventListener('input', () => {
        if (deliveryChallanNoInput.value.trim() !== '') {
            deliveryChallanDateInput.value = todayDDMMYYYY;
        } else {
            deliveryChallanDateInput.value = '';
        }
    });

    const vehicleNoInput = document.getElementById("vehicle_no");
    const transportModeInput = document.getElementById("transport_mode");
    const dateOfSupplyInput = document.getElementById("date_of_supply");
    const updateDateOfSupply = () => {
        if (vehicleNoInput.value.trim() !== '' || transportModeInput.value.trim() !== '') {
            dateOfSupplyInput.value = todayDDMMYYYY;
        } else {
            dateOfSupplyInput.value = '';
        }
    };
    vehicleNoInput.addEventListener('input', updateDateOfSupply);
    transportModeInput.addEventListener('input', updateDateOfSupply);

    const poNoInput = document.getElementById("po_no");
    const poDateInput = document.getElementById("po_date");
    poNoInput.addEventListener('input', () => {
        if (poNoInput.value.trim() !== '') {
            poDateInput.value = todayDDMMYYYY;
        } else {
            poDateInput.value = '';
        }
    });

    // 5. Auto-incrementing Invoice Number
    document.getElementById("invoice_no").value = getNextInvoiceNumber();

});