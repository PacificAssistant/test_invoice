from application.models import Document, Counterparty, Nomenclature, DocumentLine
from flask import render_template, url_for, redirect , jsonify, request, abort, flash
from sqlalchemy import func, case, and_ ,text
from sqlalchemy.orm import selectinload
from datetime import date, datetime
from decimal import Decimal
import uuid


from application import app,db
from application.models import Document, Counterparty , InventoryBalance
from application.forms import  DocumentForm, ReportForm , DocumentLineForm
from application.services.DocumentService import DocumentService
from application.services.services import DocumentPostingService
from application.services.exceptions import PostingError, InsufficientStockError
from application.services.ReportServices import ReportService
from application.services.services import DocumentStrategyFactory, InventoryManager, SequenceConfig





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
    
    im = InventoryManager(db.session)

    data = []

    for doc in documents:
        try:
            strategy = DocumentStrategyFactory.get_strategy(doc.operation_type, db.session, im)
            allowed_next = strategy.get_allowed_based_on() 
        except:
            allowed_next = []

        data.append({
            'id': doc.documents_id,
            'date': doc.document_date.strftime('%d-%m-%Y %H:%M:%S') if doc.document_date else 'Н/Д',
            'type': doc.operation_type,
            'allowed_next': allowed_next,
            'counterparty_name': doc.counterparty.counterparty_name if doc.counterparty else 'Немає',
            'amount': doc.total_amount,
            'currency': doc.currency,
            'actions': doc.documents_id,
            "number":doc.document_number
        })
        
    return jsonify(data)


    


@app.route('/api/document/save', methods=['POST'])
def save_document_ajax():
    data = request.json
    
    try:
        doc_id = data.get('doc_id')
        is_new = data.get('is_new')
        op_type = data['operation_type'] 
        
        if is_new:
            document = Document()
            document.documents_id = str(uuid.uuid4())
            

            next_number = DocumentService.get_next_number(op_type)
            document.document_number = next_number 
            
            document.operation_type = op_type
            db.session.add(document)
        else:
            document = db.session.get(Document, doc_id)
            if not document:
                return jsonify({'status': 'error', 'message': 'Документ не знайдено'}), 404


        doc_date = datetime.strptime(data['date'], '%Y-%m-%d')

        current_time = datetime.now().time()
        if not is_new and document.document_date:
             current_time = document.document_date.time()
             
        document.document_date = datetime.combine(doc_date.date(), current_time)
        
        document.operation_type = data['operation_type']
        document.counterparty_id = data.get('counterparty_id') or None
        document.currency = 'UAH'
        


        db.session.flush() 
        existing_lines = {line.product_item_id: line for line in document.lines}
        processed_ids = []
        total_doc_sum = 0
        
        for row in data['lines']:
            line_id = row.get('line_id')
            qty = float(row['quantity'])
            price = float(row['price']) 
            nom_id = row['nomenclature_id']
            vat_rate = float(row.get('vat_rate', 20.0))
            
            amounts = DocumentService.calculate_line_amounts(qty, price, vat_rate)
            total_doc_sum += amounts['total_without_vat']

            if line_id and line_id in existing_lines:

                line = existing_lines[line_id]

                line.is_deleted = False

                line.nomenclature_id = nom_id
                line.quantity = qty
                line.price_with_vat = price
                line.vat_rate = vat_rate
                line.total_with_vat = amounts['total_with_vat']
                line.vat_amount = amounts['vat_amount']
                line.total_amount = amounts['total_without_vat']
                
                processed_ids.append(line_id)
            else:

                new_line_id = str(uuid.uuid4())
                new_line = DocumentLine(
                    product_item_id=new_line_id,
                    document_id=document.documents_id,
                    nomenclature_id=nom_id,
                    quantity=qty,
                    price_with_vat=price,
                    vat_rate=vat_rate,
                    total_with_vat=amounts['total_with_vat'],
                    vat_amount=amounts['vat_amount'],
                    total_amount=amounts['total_without_vat'],
                    unit="шт."
                )
                db.session.add(new_line)

        for old_id, old_line in existing_lines.items():
            if old_id not in processed_ids:
                old_line.is_deleted = True
                
                old_line.quantity = 0
                old_line.total_amount = 0
                old_line.total_with_vat = 0
                old_line.vat_amount = 0


        
        document.total_amount = total_doc_sum
        db.session.commit()
        
        return jsonify({
            'status': 'success', 
            'message': 'Збережено!', 
            'doc_id': document.documents_id,
            'doc_number': document.document_number
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/document/<string:doc_id>/post', methods=['POST'])
def post_document(doc_id):
    posting_service = DocumentPostingService(db.session)

    try:
        posting_service.post_document(doc_id)
        return jsonify({'status': 'success', 'message': 'Документ успішно проведено (FIFO)!'})
        
    except InsufficientStockError as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': f'Помилка залишків: {str(e)}'}), 400
        
    except PostingError as e:

        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 400
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': f'Системна помилка: {str(e)}'}), 500


@app.route('/document/new')
@app.route('/document/<string:doc_id>')
def document_card(doc_id=None):
    counterparties = db.session.execute(db.select(Counterparty)).scalars().all()
    nomenclatures = db.session.execute(db.select(Nomenclature)).scalars().all()

    document = None
    can_be_posted = False
    available_action = None
    doc_types = DocumentForm.DOC_TYPES
    lines = []
    

    next_id = "(Авто)" 


    is_edit_mode = (doc_id is not None and doc_id != 'new')

    if is_edit_mode: 
        document = db.session.execute(
            db.select(Document).filter_by(documents_id=doc_id)
        ).scalar_one_or_none()
        

        if not document:
            abort(404, description="Документ не знайдено")


        next_id = document.document_number
        
        lines = db.session.execute(
            db.select(DocumentLine)
            .filter_by(document_id=doc_id, is_deleted=False)
            .options(selectinload(DocumentLine.nomenclature))
        ).scalars().all()

        if document.operation_type in ["Прибуткова накладна", "Видаткова накладна"]:
            can_be_posted = True

        im = InventoryManager(db.session)
        strategy = DocumentStrategyFactory.get_strategy(document.operation_type, db.session, im)
        
        next_type = strategy.next_document_type
        if next_type:
            available_action = {
                'label': next_type, 
                'url': url_for('create_based_on', source_id=document.documents_id)
            }


    return render_template(
        'document_card.html',
        document=document,
        lines=lines,
        counterparties=counterparties,
        nomenclatures=nomenclatures,
        doc_id=doc_id if doc_id else 'new',
        next_id=next_id, # Тепер ця змінна гарантовано існує
        today_date=date.today(),
        doc_types=doc_types,
        available_action=available_action,
        can_be_posted=can_be_posted
    )

@app.route('/document/<string:source_id>/create_next')
def create_based_on(source_id):
    """
    Універсальний метод створення наступного документа в ланцюжку.
    """

    source_doc = db.session.execute(
        db.select(Document).filter_by(documents_id=source_id)
        .options(selectinload(Document.lines))
    ).scalar_one_or_none()

    if not source_doc:
        flash("Документ-підставу не знайдено", "error")
        return redirect(url_for('documents_list'))

    im = InventoryManager(db.session)
    strategy = DocumentStrategyFactory.get_strategy(source_doc.operation_type, db.session, im)
    target_type = strategy.next_document_type

    if not target_type:
        flash(f"Для документа типу '{source_doc.operation_type}' не передбачено створення на підставі.", "warning")
        return redirect(url_for('document_card', doc_id=source_id))

    
    counterparties = db.session.execute(db.select(Counterparty)).scalars().all()
    nomenclatures = db.session.execute(db.select(Nomenclature)).scalars().all()
    

    new_doc = Document(
        document_date=datetime.now(),
        operation_type=target_type,
        counterparty_id=source_doc.counterparty_id,
        contract_name=f"Основ.: {source_doc.operation_type} №{source_doc.documents_id}"
    )

    lines_data = []
    for line in source_doc.lines:
        
        lines_data.append(line) 

    flash(f"Створення '{target_type}' на підставі '{source_doc.operation_type} №{source_doc.document_number}'", "info")

    return render_template(
        'document_card.html',
        document=new_doc,           
        lines=lines_data,           
        counterparties=counterparties,
        nomenclatures=nomenclatures,
        doc_id='new',               
        next_id='(Авто)',
        today_date=date.today(),
        doc_types=DocumentForm.DOC_TYPES
    )




@app.route('/inventory')
def inventory_list():
    query = db.select(InventoryBalance)\
        .join(InventoryBalance.nomenclature)\
        .filter(InventoryBalance.quantity > 0)\
        .order_by(
            Nomenclature.nomenclature_name, 
            InventoryBalance.batch_date
        )


    balances = db.session.execute(query).scalars().all()

    return render_template('inventory_list.html', balances=balances)




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

    im = InventoryManager(db.session)
    strategy = DocumentStrategyFactory.get_strategy(document.operation_type, db.session, im)
    
    # Рендеримо спеціальний шаблон для друку
    return render_template('print_document.html', document=document, lines=lines, strategy=strategy)