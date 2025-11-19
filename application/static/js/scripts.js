
function addLine() {
    const container = document.getElementById('lines-container');
    
    if (!container) return;

    const firstRow = container.children[0];
    const newIndex = container.children.length;

    // Клонуємо перший рядок
    const newRow = firstRow.cloneNode(true);
    
    // Оновлюємо атрибут data-line-index
    newRow.setAttribute('data-line-index', newIndex);

    // Знаходимо всі input та select у новому рядку і оновлюємо їх ID та Name
    const inputs = newRow.querySelectorAll('input, select, label');

    inputs.forEach(input => {
        // Замінюємо індекс 0 на новий (наприклад, lines-0-... стає lines-1-...)
        // Регулярний вираз /-0-/g замінює всі входження "-0-"
        if (input.name) {
            input.name = input.name.replace(/-0-/g, '-' + newIndex + '-');
        }
        if (input.id) {
            input.id = input.id.replace(/-0-/g, '-' + newIndex + '-');
        }
        if (input.htmlFor) {
            input.htmlFor = input.htmlFor.replace(/-0-/g, '-' + newIndex + '-');
        }

        // Скидаємо значення полів
        if (input.tagName === 'INPUT') {
            if (input.type === 'number') {
                // Якщо це кількість - ставимо 1, якщо ціна/сума - 0
                if(input.name.includes('quantity')) input.value = "1";
                else input.value = "0.00";
            } else {
                input.value = "";
            }
        }
        if (input.tagName === 'SELECT') {
            input.selectedIndex = 0; // Скидаємо вибір
        }
    });

    // Додаємо кнопку видалення (якщо її ще немає в клоні або треба оновити)
    const removeContainer = newRow.querySelector('.remove-btn-container');
    if (removeContainer) {
        removeContainer.innerHTML = `<button type="button" class="btn-remove" onclick="removeLine(this)">X</button>`;
    }

    container.appendChild(newRow);
}

// Функція видалення рядка
function removeLine(button) {
    const row = button.closest('.line-row');
    if (row) {
        row.remove();
    }
}


document.addEventListener("DOMContentLoaded", function() {
    
    // 1. Функція для форматування колонки "Дії"
    var actionsFormatter = function(cell, formatterParams, onRender){
        var docId = cell.getValue(); 
        
        if(!docId) {
            docId = cell.getData().id;
        }

        var viewUrl = "/document/" + docId;
        var editUrl = "/document/edit/" + docId;
        
        return `
            <a href="${viewUrl}">Переглянути</a> | 
            <a href="${editUrl}">Редагувати</a>
        `;
    };

    // 2. Ініціалізація Tabulator
    var table = new Tabulator("#documents-table", {
        ajaxURL: "/api/documents",
        layout: "fitColumns",
        pagination: "local",
        paginationSize: 10,
        
        columns: [
            {title: "ID", field: "id", width: 80, sorter: "string"},
            {
                title: "Дата", 
                field: "date", 
                width: 160,
                sorter: "datetime",
                sorterParams: {
                    format: "yyyy-MM-dd HH:mm:ss",
                    alignEmptyValues: "top",
                },
                headerFilter: "input", 
            },
            {title: "Тип Операції", field: "type", sorter: "string"},
            {title: "Контрагент", field: "counterparty_name", sorter: "string"},
            {title: "Сума", field: "amount", sorter: "number", hozAlign: "right"},
            {title: "Валюта", field: "currency", width: 80, hozAlign: "center"},
            
            // Колонка дій
            {title: "Дії", field: "id", formatter: actionsFormatter, width: 180, hozAlign: "center", headerSort: false},
        ],
    });

});