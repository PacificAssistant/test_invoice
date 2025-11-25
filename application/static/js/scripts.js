
function showFlashToasts(messages) {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    messages.forEach(([category, message]) => {
        let bgClass = 'text-bg-primary';
        let title = 'Повідомлення';

        if (category === 'success') {
            bgClass = 'text-bg-success';
            title = 'Успіх';
        } else if (category === 'error' || category === 'danger') {
            bgClass = 'text-bg-danger';
            title = 'Помилка';
        } else if (category === 'warning') {
            bgClass = 'text-bg-warning text-dark';
            title = 'Увага';
        }

        const toastHtml = `
            <div class="toast ${bgClass}" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="toast-header">
                    <strong class="me-auto">${title}</strong>
                    <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
                <div class="toast-body">${message}</div>
            </div>
        `;

        container.insertAdjacentHTML('beforeend', toastHtml);
        const newToastElement = container.lastElementChild;
        const toast = new bootstrap.Toast(newToastElement, { delay: 5000 });
        toast.show();
    });
}

var actionsFormatter = function(cell, formatterParams, onRender){
    var rowData = cell.getData();
    var docId = rowData.id;
    var allowedNext = rowData.allowed_next || [];
    
    var buttons = `<div style="display: flex; gap: 5px; justify-content: center;">`;
    

    buttons += `<a href="/document/${docId}" class="btn btn-sm btn-info">👁️</a>`;
    

    buttons += `<a href="/document/${docId}/print" target="_blank" class="btn btn-sm btn-secondary">🖨️</a>`;


    allowedNext.forEach(nextType => {
        let url = "#";
        let icon = "📄";
        let title = "Створити " + nextType;

        if(nextType === 'Рахунок фактура') {
            url = `/document/${docId}/create_invoice`;
            icon = "💰";
        } else if (nextType === 'Видаткова накладна') {
             url = `/document/${docId}/create_outgoing`;
             icon = "📦";
        } else if (nextType === 'Податкова накладна') {
             url = `/document/${docId}/create_tax_invoice`;
             icon = "🏛️";
        }

        buttons += `<a href="${url}" class="btn btn-sm btn-warning" title="${title}">${icon}</a>`;
    });

    buttons += `</div>`;
    return buttons;
};


let saveButtonElement = null;

document.addEventListener('DOMContentLoaded', () => {
    

    saveButtonElement = document.querySelector('button[onclick="saveDocument()"]');


    if (!window.documentContext) return;

    const { existingLines, isNew } = window.documentContext;


    if (existingLines && existingLines.length > 0) {
        existingLines.forEach(line => addRow(line));
    } else {
        addRow(); 
    }
    calcTotal();


    if (!isNew && saveButtonElement) {
        saveButtonElement.disabled = true;
        saveButtonElement.innerText = "Збережено"; 
    }


    const headerInputs = document.querySelectorAll('#docDate, #counterparty, #opType');
    headerInputs.forEach(input => {
        input.addEventListener('change', markAsDirty);
        input.addEventListener('input', markAsDirty);
    });
});


function markAsDirty() {
    if (saveButtonElement) {
        saveButtonElement.disabled = false;
        saveButtonElement.innerText = "Зберегти"; 
        
        // Прибираємо клас успіху, якщо він був (опціонально)
        const statusSpan = document.getElementById('statusMessage');
        if (statusSpan) statusSpan.innerText = "";
    }
}


function recalcRow(input) {
    markAsDirty(); 

    const tr = input.closest('tr');
    const qty = parseFloat(tr.querySelector('.input-qty').value) || 0;
    const price = parseFloat(tr.querySelector('.input-price').value) || 0; 
    const vatRate = parseFloat(tr.querySelector('.input-vat').value) || 0; 

    const priceWithVat = price * (1 + vatRate / 100);
    const sum = (qty * priceWithVat).toFixed(2);
    
    tr.querySelector('.row-sum').innerText = sum;
    calcTotal();
}


function calcTotal() {
    let total = 0;
    const sums = document.querySelectorAll('.row-sum');
    if(sums) {
        sums.forEach(span => {
            total += parseFloat(span.innerText);
        });
        const totalElem = document.getElementById('totalSum');
        if(totalElem) totalElem.innerText = total.toFixed(2);
    }
}

function removeRow(btn) {
    markAsDirty();
    btn.closest('tr').remove();
    calcTotal();
}
async function saveDocument() {

    const btnSave = document.getElementById('btnSave');
    let originalBtnContent = '';

    if (btnSave) {
        originalBtnContent = btnSave.innerHTML; 
        btnSave.disabled = true; 

        btnSave.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Запис...';
    }
    
    const restoreButton = () => {
        if (btnSave) {
            btnSave.disabled = false;
            btnSave.innerHTML = originalBtnContent;
        }
    };

    if (!window.documentContext) {
        console.error("Помилка: documentContext не знайдено");
        restoreButton();
        return;
    }
    const { docId, isNew } = window.documentContext;
    
    const counterpartyVal = document.getElementById('counterparty').value;
    if (!counterpartyVal) {
        alert("Будь ласка, оберіть контрагента!");
        restoreButton();
        return;
    }

    const rows = [];
    document.querySelectorAll('#linesTable tbody tr').forEach(tr => {
        const nomId = tr.querySelector('.input-nom').value;
        const lineId = tr.querySelector('.input-line-id').value; 
        
        if (nomId) {
            rows.push({
                line_id: lineId || null, 
                nomenclature_id: nomId,
                quantity: tr.querySelector('.input-qty').value,
                price: tr.querySelector('.input-price').value,
                vat_rate: tr.querySelector('.input-vat').value,
            });
        }
    });

    if (rows.length === 0) {
        alert("Документ повинен містити хоча б один товар!");
        restoreButton();
        return;
    }

    const payload = {
        doc_id: isNew ? null : docId,
        is_new: isNew,
        date: document.getElementById('docDate').value,
        operation_type: document.getElementById('opType').value,
        counterparty_id: counterpartyVal,
        lines: rows
    };

    const statusSpan = document.getElementById('statusMessage');
    if (statusSpan) statusSpan.innerText = "Збереження...";

    try {
        const response = await fetch('/api/document/save', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            if (statusSpan) {
                statusSpan.innerText = "Збережено!";
                statusSpan.className = "text-success ms-auto align-self-center";
            }
            
            if (isNew) {
                window.location.href = `/document/${result.doc_id}`;
            } else {
                // window.location.reload(); 
                if (btnSave) {
                    btnSave.disabled = true;
                    btnSave.innerText = "Збережено";
                }
            }
            
        } else {

            alert("Помилка: " + result.message);
            if (statusSpan) {
                statusSpan.innerText = "Помилка!";
                statusSpan.className = "text-danger ms-auto align-self-center";
            }
            restoreButton();
        }
    } catch (error) {

        console.error(error);
        alert("Системна помилка збереження. Перевірте консоль.");
        restoreButton();
    }
}


async function postDocument() {
    if (!window.documentContext) return;
    const { docId, isNew } = window.documentContext;

    if (isNew) {
        alert("Спочатку збережіть документ!");
        return;
    }
    
    if (!confirm("Провести документ? Це змінить залишки.")) return;

    const statusSpan = document.getElementById('statusMessage');
    if (statusSpan) statusSpan.innerText = "Проведення...";
    
    try {
        const response = await fetch(`/api/document/${docId}/post`, {
            method: 'POST'
        });
        const result = await response.json();
        
        if (result.status === 'success') {
            alert("Успішно проведено!");
            location.reload(); 
        } else {
            alert("Помилка проведення: " + result.message);
        }
    } catch (e) {
        alert("Помилка з'єднання");
    }
}

function addRow(data = null) {
    const nomenclatureList = window.documentContext.nomenclatures;
    const tbody = document.querySelector('#linesTable tbody');
    if (!tbody) return;


    const tr = document.createElement('tr');

    const lineId = data ? data.product_item_id : "";
    let optionsHtml = '<option value="">Оберіть товар...</option>';
    nomenclatureList.forEach(n => {
        const selected = (data && String(data.nom_id) === String(n.id)) ? 'selected' : '';
        optionsHtml += `<option value="${n.id}" ${selected}>${n.name}</option>`;
    });

    const qty = data ? data.qty : 1;
    const price = data ? data.price : 0;
    const vat = data ? data.vat : 20;
    const sum = (qty * price).toFixed(2);

    tr.innerHTML = `
        <td>
            <select class="form-select form-select-sm border-0 input-nom" onchange="markAsDirty()">${optionsHtml}</select> </td>
        <td>
            <input type="number" step="0.001" class="table-input input-qty" value="${qty}" oninput="recalcRow(this)">
        </td>
        <td>
            <input type="number" step="1" class="table-input input-vat" value="${vat}" oninput="recalcRow(this)">
        </td>
        <td>
            <input type="number" step="0.01" class="table-input input-price" value="${price}" oninput="recalcRow(this)">
        </td>
        <td class="align-middle">
            <span class="row-sum">${sum}</span>
        </td>
        <td class="text-center">
            <button class="btn btn-xs text-danger" onclick="removeRow(this)">x</button>
        </td>
        <td>
            <input type="hidden" class="input-line-id" value="${lineId}">
        </td>
    `;
    tbody.appendChild(tr);


    if (!data) {
        markAsDirty();
    }
}



document.addEventListener("DOMContentLoaded", function() {

    var tableElement = document.getElementById("documents-table");
    if (!tableElement) {
        return; 
    }

    var actionsFormatter = function(cell, formatterParams, onRender){
        var docId = cell.getData().id;
        var docType = cell.getData().type; 
        
        // Проста логіка на клієнті для іконок (хоча краще керувати з сервера)
        let nextIcon = "";
        if (["Замовлення", "Рахунок фактура", "Видаткова накладна"].includes(docType)) {
            nextIcon = `<a href="/document/${docId}/create_next" class="btn btn-sm btn-warning" title="Створити на підставі">➥</a>`;
        }

        return `
            <div style="display: flex; gap: 5px; justify-content: center;">
                <a href="/document/${docId}" class="btn btn-sm btn-info">👁️</a>
                ${nextIcon}
            </div>
        `;
    };

    var table = new Tabulator("#documents-table", {
        ajaxURL: "/api/documents",
        layout: "fitColumns",
        pagination: "local",
        paginationSize: 10,
        placeholder:"Немає даних",
        
        columns: [
            {title: "ID", field: "number", width: 80, sorter: "string"},
            {
                title: "Дата", 
                field: "date", 
                width: 160,
                sorter: "datetime",
                sorterParams: { format: "dd-MM-yyyy HH:mm:ss" },
                headerFilter: "input", 
            },
            {title: "Тип Операції", field: "type", sorter: "string"},
            {title: "Контрагент", field: "counterparty_name", sorter: "string"},
            {title: "Сума", field: "amount", sorter: "number", hozAlign: "right"},
            {title: "Валюта", field: "currency", width: 80, hozAlign: "center"},
            {title: "Дії", field: "id", formatter: actionsFormatter, width: 120, hozAlign: "center", headerSort: false},
        ],
    });
});


