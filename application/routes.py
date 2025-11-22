from application.models import Document, Counterparty, Nomenclature, DocumentLine
from flask import render_template, url_for, redirect , jsonify, request, abort, flash
from sqlalchemy import func, case, and_
from sqlalchemy.orm import selectinload
from datetime import date, datetime
from decimal import Decimal
import uuid


from application import app,db
from application.models import Document, Counterparty , InventoryBalance
from application.forms import  DocumentForm, ReportForm
from application.services.DocumentService import DocumentService
from application.services.services import DocumentPostingService
from application.services.exceptions import PostingError, InsufficientStockError
from application.services.ReportServices import ReportService





@app.route('/')
@app.route('/documents')
def documents_list():

    documents = db.session.execute(
        db.select(Document)
        .order_by(Document.document_date.desc(), Document.documents_id.desc())
    ).scalars().all()
    

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
                nomenclature_id = line_form.data['nomenclature_id'] 
                
                # Розрахунки
                amounts = DocumentService.calculate_line_amounts(quantity, price_with_vat)
                total_doc_amount_without_vat += amounts['total_without_vat']
                
                # Створення запису DocumentLine 
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
                total_amount=round(total_doc_amount_without_vat, 2),
                currency="UAH",
                counterparty_id=counterparty_id,
                
            )
            db.session.add(new_document)
            
            # 5. Збереження та Перенаправлення
            db.session.commit()
            print(f'Документ {doc_id} успішно створено!', 'success')
            return redirect(url_for('documents_list'))

        except Exception as e:
            db.session.rollback()
            print(f"Помилка при збереженні документа. Деталі: {e}", 'error')
 
        

    return render_template('create_document.html', 
                            form=form, 
                            nomenclatures=nomenclatures_data) 


    
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




@app.route('/document/<string:doc_id>/post', methods=['POST'])
def post_document(doc_id):
    posting_service = DocumentPostingService(db.session)

    try:
        posting_service.post_document(doc_id)
        flash('Документ успішно проведено (FIFO)!', 'success')
        
    except InsufficientStockError as e:
        # Специфічна помилка залишків
        db.session.rollback()
        flash(f'Помилка залишків: {str(e)}', 'error')
        
    except PostingError as e:
        # Загальна помилка логіки (вже проведено, не той тип тощо)
        db.session.rollback()
        flash(f'Неможливо провести документ: {str(e)}', 'warning')
        
    except Exception as e:
        # Непередбачена технічна помилка
        db.session.rollback()
        flash(f'Системна помилка: {str(e)}', 'error')
        # Тут можна додати логування помилки

    return redirect(url_for('view_document', doc_id=doc_id))

@app.route('/inventory')
def inventory_list():
    # Отримуємо всі залишки. Завдяки lazy="joined" у моделі, 
    # дані про номенклатуру підтягнуться автоматично.
    balances = db.session.execute(
        db.select(InventoryBalance)
        .join(InventoryBalance.nomenclature) 
        .order_by(Nomenclature.nomenclature_name)
    ).scalars().all()

    return render_template('inventory_list.html', balances=balances)






def _handle_document_creation_based_on(source_id, target_type, contract_name_generator, success_message):
    """
    Універсальна функція для створення документа на підставі іншого.
    
    :param source_id: ID документа-підстави
    :param target_type: Тип нового документа (напр. 'Видаткова накладна')
    :param contract_name_generator: Функція (lambda), яка приймає source_doc і повертає рядок 'contract_name'
    :param success_message: Текст повідомлення про успіх
    """
    
    # 1. Шукаємо документ-підставу
    source_doc = db.session.execute(
        db.select(Document)
        .filter_by(documents_id=source_id)
        .options(selectinload(Document.lines))
    ).scalar_one_or_none()

    if not source_doc:
        abort(404)

    # Завантажуємо довідники (для форми)
    counterparties = db.session.execute(db.select(Counterparty).order_by(Counterparty.counterparty_name)).scalars().all()
    nomenclatures = db.session.execute(db.select(Nomenclature).order_by(Nomenclature.nomenclature_name)).scalars().all()


    form = DocumentForm(request.form)
    form.counterparty_id.choices = [('', 'Оберіть контрагента')] + [
        (str(cp.counterparty_id), cp.counterparty_name) for cp in counterparties
    ]

    #  GET: Заповнення форми даними з джерела
    if request.method == 'GET':
        form.operation_type.data = target_type
        form.counterparty_id.data = source_doc.counterparty_id
        
        # Очищення та заповнення рядків
        while len(form.lines) > 0:
            form.lines.pop_entry()
            
        for line in source_doc.lines:
            form.lines.append_entry({
                'nomenclature_id': line.nomenclature_id,
                'quantity': line.quantity,
                'price_with_vat': line.price_with_vat
            })

    #  POST: Збереження через Service Layer
    if request.method == 'POST' and form.validate_on_submit():
        try:
            # Генеруємо назву договору/підстави динамічно
            contract_text = contract_name_generator(source_doc)
            
            # Викликаємо сервіс для збереження
            DocumentService.create_document_from_form(
                form=form,
                operation_type=target_type,
                contract_name=contract_text
            )
            
            flash(success_message, 'success')
            return redirect(url_for('documents_list'))
            
        except Exception as e:
            flash(f"Помилка при збереженні: {str(e)}", 'error')

    return render_template('create_document.html', form=form, nomenclatures=nomenclatures)



@app.route('/document/<string:source_id>/create_invoice', methods=['GET', 'POST'])
def create_invoice_based_on(source_id):
    return _handle_document_creation_based_on(
        source_id=source_id,
        target_type="Рахунок фактура",
        contract_name_generator=lambda src: f"На підставі {src.operation_type} від {src.document_date.date()}",
        success_message="Рахунок фактура успішно створений!"
    )

@app.route('/document/<string:source_id>/create_outgoing', methods=['GET', 'POST'])
def create_outgoing_based_on(source_id):
    return _handle_document_creation_based_on(
        source_id=source_id,
        target_type="Видаткова накладна",
        contract_name_generator=lambda src: f"На підставі {src.operation_type} №{src.documents_id[:8]}",
        success_message="Видаткову накладну успішно створено!"
    )

@app.route('/document/<string:source_id>/create_tax_invoice', methods=['GET', 'POST'])
def create_tax_invoice_based_on(source_id):
    return _handle_document_creation_based_on(
        source_id=source_id,
        target_type="Податкова накладна",
        contract_name_generator=lambda src: f"Податкова накладна до {src.operation_type} №{src.documents_id[:8]}",
        success_message="Податкову накладну успішно створено!"
    )





@app.route('/reports', methods=['GET', 'POST'])
def reports():
    form = ReportForm(request.form)
    results = []
    report_type = None
    total_sum = 0.0
    
    report_service = ReportService(db.session)

    if request.method == 'POST' and form.validate():
        # Нормалізація дат
        start_date = datetime.combine(form.start_date.data, datetime.min.time())
        end_date = datetime.combine(form.end_date.data, datetime.max.time())
        report_type = form.report_type.data

        if report_type == 'sales':
            results = report_service.get_sales_report(start_date, end_date)
            # Рахуємо суму тут або теж можна винести в сервіс
            total_sum = sum(row.total_amount for row in results)

        elif report_type == 'inventory_date':
            # Для цього звіту важлива тільки кінцева дата
            results = report_service.get_inventory_on_date(end_date)
            # Тут total_sum це загальна вартість складу
            total_sum = sum(row.balance_sum for row in results)

    return render_template(
        'reports.html', 
        form=form, 
        results=results, 
        report_type=report_type, 
        total_sum=total_sum
    )

@app.route('/document/<string:doc_id>/print')
def print_document_page(doc_id):
    # Завантажуємо документ з контрагентом
    document = db.session.execute(
        db.select(Document)
        .filter_by(documents_id=doc_id)
        .options(selectinload(Document.counterparty))
    ).scalar_one_or_none()

    if document is None:
        abort(404) 

    # Завантажуємо рядки
    lines = db.session.execute(
        db.select(DocumentLine)
        .filter_by(document_id=doc_id)
        .options(selectinload(DocumentLine.nomenclature))
        .order_by(DocumentLine.product_item_id)
    ).scalars().all()
    
    # Рендеримо спеціальний шаблон для друку
    return render_template('print_document.html', document=document, lines=lines)