from application.models import Document, Counterparty, Nomenclature, DocumentLine
from flask import render_template, url_for, redirect , jsonify, request, abort, flash
from sqlalchemy.orm import selectinload
from datetime import date, datetime
import uuid

from application import app,db
from application.models import Document, Counterparty 
from application.forms import DocumentLineForm, DocumentForm


@app.route('/')
@app.route('/documents')
def documents_list():

    documents = db.session.execute(
        db.select(Document)
        .order_by(Document.document_date.desc(), Document.documents_id.desc())
    ).scalars().all()
    
    # Рендеринг шаблону, передаючи список документів
    return render_template('documents_list_tabulator.html', documents=documents)


@app.route('/api/documents')
def documents_api():
    documents = db.session.execute(
        db.select(Document)
        .options(selectinload(Document.counterparty)) 
        .order_by(Document.document_date.desc(), Document.documents_id.desc())
    ).scalars().all()
    

    data = []
    for doc in documents:
        data.append({
            'id': doc.documents_id,
            'date': doc.document_date.strftime('%Y-%m-%d %H:%M:%S') if doc.document_date else 'Н/Д',
            'type': doc.operation_type,
            'counterparty_name': doc.counterparty.counterparty_name if doc.counterparty else 'Немає',
            'amount': doc.total_amount,
            'currency': doc.currency,
            'actions': doc.documents_id # Потрібно для генерації посилань
        })
        
    return jsonify(data)


def calculate_line_amounts(quantity, price_with_vat):
    VAT_RATE = 0.20 # 20%
    VAT_MULTIPLIER = 1 + VAT_RATE
    """Виконує розрахунки сум для одного рядка документа."""
    price_without_vat = price_with_vat / VAT_MULTIPLIER
    total_with_vat = quantity * price_with_vat
    total_without_vat = quantity * price_without_vat
    vat_amount = total_with_vat - total_without_vat
    
    return {
        'price_without_vat': price_without_vat,
        'total_without_vat': total_without_vat,
        'total_with_vat': total_with_vat,
        'vat_amount': vat_amount,
    }

@app.route('/document/new', methods=['GET', 'POST'])
def create_document():
    # 1. Завантаження даних для списків
    counterparties_data = db.session.execute(
        db.select(Counterparty).order_by(Counterparty.counterparty_name)
    ).scalars().all()
    
    nomenclatures_data = db.session.execute(
        db.select(Nomenclature).order_by(Nomenclature.nomenclature_name)
    ).scalars().all()

    # Створюємо форму та заповнюємо динамічні choices
    form = DocumentForm(request.form)
    
    # Заповнення choices для контрагентів: [(id, name), ...]
    form.counterparty_id.choices = [
        ('', 'Оберіть контрагента')
    ] + [
        (str(cp.counterparty_id), cp.counterparty_name) 
        for cp in counterparties_data
    ]

    print("FORM DATA:", request.form)
    if form.validate_on_submit():
        try:
            doc_id = str(uuid.uuid4())
            
            # 2. Збір даних із валідованої форми
            doc_date_data = form.document_date.data # Це вже об'єкт date
            operation_type = form.operation_type.data
            counterparty_id = form.counterparty_id.data
            
            # Об'єднання дати та поточного часу
            doc_date = datetime.combine(doc_date_data, datetime.now().time())
            
            total_doc_amount_without_vat = 0.0
            
            # 3. Обробка Рядків Документа
            for line_form in form.lines.entries:
                
                # Дані вже перетворені у float завдяки WTForms
                quantity = line_form.data['quantity']
                price_with_vat = line_form.data['price_with_vat']
                nomenclature_id = line_form.data['nomenclature_id'] # Вимагає обробки в HTML
                
                # Розрахунки
                amounts = calculate_line_amounts(quantity, price_with_vat)
                total_doc_amount_without_vat += amounts['total_without_vat']
                
                # Створення запису DocumentLine (використовуємо числові значення)
                new_line = DocumentLine(
                    product_item_id=str(uuid.uuid4()),
                    document_id=doc_id,
                    nomenclature_id=nomenclature_id,
                    quantity=quantity,
                    unit="шт.", 
                    price_with_vat=round(price_with_vat, 2),
                    total_with_vat=round(amounts['total_with_vat'], 2),
                    vat_amount=round(amounts['vat_amount'], 2), 
                    total_amount=round(amounts['total_without_vat'], 2),
                )
                db.session.add(new_line)
            
            # 4. Створення Заголовка Документа
            new_document = Document(
                documents_id=doc_id,
                document_date=doc_date,
                operation_type=operation_type,
                amount=round(total_doc_amount_without_vat, 2),
                currency="UAH",
                counterparty_id=counterparty_id,
                # is_posted=False за замовчуванням
            )
            db.session.add(new_document)
            
            # 5. Збереження та Перенаправлення
            db.session.commit()
            flash(f'Документ {doc_id} успішно створено!', 'success')
            return redirect(url_for('documents_list'))

        except Exception as e:
            db.session.rollback()
            flash(f"Помилка при збереженні документа. Деталі: {e}", 'error')
            # Форма автоматично відобразить помилки валідації полів
    else:
        # ДОДАЙТЕ ЦЕЙ РЯДОК, щоб бачити чому форма не проходить
        print("VALIDATION ERRORS:", form.errors)
    # GET request або POST request з помилкою валідації форми
    return render_template('create_document.html', 
                            form=form, 
                            nomenclatures=nomenclatures_data) # Передаємо номенклатуру для JS/HTML таблиці
@app.route('/document/<string:doc_id>')
def view_document(doc_id):
    # 1. Завантажуємо Заголовок Документа
    # Використовуємо joinedload для завантаження пов'язаного Контрагента одним запитом
    document = db.session.execute(
        db.select(Document)
        .filter_by(documents_id=doc_id)
        .options(selectinload(Document.counterparty))
    ).scalar_one_or_none()

    if document is None:
        # Якщо документ не знайдено, повертаємо помилку 404
        abort(404) 

    # 2. Завантажуємо Рядки Документа (Номенклатуру)
    # Використовуємо selectinload для завантаження пов'язаної Номенклатури для кожного рядка
    lines = db.session.execute(
        db.select(DocumentLine)
        .filter_by(document_id=doc_id)
        .options(selectinload(DocumentLine.nomenclature))
        .order_by(DocumentLine.product_item_id) # Сортування за ID рядка
    ).scalars().all()
    
    # 3. Передаємо дані в шаблон
    return render_template('view_document.html', document=document, lines=lines)

@app.route('/document/edit/<string:doc_id>')
def edit_document(doc_id):
    return f"<h1>Редагування документа ID: {doc_id} (У розробці)</h1>"

