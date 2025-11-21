// application/static/js/scripts.js

// 1. Функція додавання рядка (використовується у create_document.html)
function addLine() {
    const container = document.getElementById('lines-container');
    if (!container) return;

    const firstRow = container.children[0];
    const newIndex = container.children.length;

    // Клонуємо перший рядок
    const newRow = firstRow.cloneNode(true);
    newRow.setAttribute('data-line-index', newIndex);

    const inputs = newRow.querySelectorAll('input, select, label');
    inputs.forEach(input => {
        if (input.name) input.name = input.name.replace(/-0-/g, '-' + newIndex + '-');
        if (input.id) input.id = input.id.replace(/-0-/g, '-' + newIndex + '-');
        if (input.htmlFor) input.htmlFor = input.htmlFor.replace(/-0-/g, '-' + newIndex + '-');

        if (input.tagName === 'INPUT') {
            if (input.type === 'number') {
                if(input.name.includes('quantity')) input.value = "1";
                else input.value = "0.00";
            } else {
                input.value = "";
            }
        }
        if (input.tagName === 'SELECT') input.selectedIndex = 0;
    });

    const removeContainer = newRow.querySelector('.remove-btn-container');
    if (removeContainer) {
        removeContainer.innerHTML = `<button type="button" class="btn-remove" onclick="removeLine(this)">X</button>`;
    }
    container.appendChild(newRow);
}

// 2. Функція видалення рядка
function removeLine(button) {
    const row = button.closest('.line-row');
    if (row) row.remove();
}

// 3. Функція показу повідомлень (Toasts)
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

// 4. Ініціалізація Tabulator (ТІЛЬКИ ЯКЩО Є ТАБЛИЦЯ)
document.addEventListener("DOMContentLoaded", function() {
    
    // !!! ВАЖЛИВА ПЕРЕВІРКА !!!
    // Якщо на сторінці немає таблиці (наприклад, це сторінка створення), ми виходимо.
    // Інакше Tabulator видасть помилку, і інші скрипти (FlashToasts) не запустяться.
    var tableElement = document.getElementById("documents-table");
    if (!tableElement) {
        return; 
    }

    var actionsFormatter = function(cell, formatterParams, onRender){
        var docId = cell.getValue(); 
        if(!docId) docId = cell.getData().id;
        
        var viewUrl = "/document/" + docId;
        // ЗМІНЕНО: Посилання на друк замість редагування
        var printUrl = "/document/" + docId + "/print"; 
        
        return `
            <div style="display: flex; gap: 5px; justify-content: center;">
                <a href="${viewUrl}" class="btn btn-sm btn-info" title="Перегляд" style="padding: 2px 8px; font-size: 12px;">👁️</a>
                <a href="${printUrl}" target="_blank" class="btn btn-sm btn-secondary" title="Друк А4" style="padding: 2px 8px; font-size: 12px;">🖨️</a>
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
            {title: "ID", field: "id", width: 80, sorter: "string"},
            {
                title: "Дата", 
                field: "date", 
                width: 160,
                sorter: "datetime",
                sorterParams: { format: "yyyy-MM-dd HH:mm:ss" },
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