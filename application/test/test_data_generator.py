# app/test_data_generator.py
import uuid
import random
from datetime import date, timedelta,datetime
from application import db 
from application.models import Counterparty, Nomenclature, Document, DocumentLine 

def create_test_data():
    """Створює тестові дані (контрагенти, номенклатура, 100 документів) 
    у базі даних, якщо вони ще не існують.
    """
    # Перевірка, чи база даних вже містить дані (щоб не дублювати)
    if Counterparty.query.first() and Document.query.first():
        print("Тестові дані вже існують. Пропускаємо генерацію.")
        return
    
    print("Генерація 100 тестових документів...")

    # 1. Створення 5 Тестових Контрагентів
    counterparties = []
    for i in range(1, 6):
        cp_id = str(uuid.uuid4())
        cp = Counterparty(counterparty_id=cp_id, counterparty_name=f"Контрагент {i} ТОВ")
        db.session.add(cp)
        counterparties.append(cp)

    # 2. Створення 10 Тестових Товарів/Послуг (Номенклатура)
    nomenclatures = []
    vat_rates = ["20%", "7%", "0%"]
    for i in range(1, 11):
        n_id = str(uuid.uuid4())
        is_service = i > 7 
        name = f"Послуга Доставки {i-7}" if is_service else f"Товар {i}"
        
        n = Nomenclature(
            nomenclature_id=n_id, 
            nomenclature_name=name, 
            vat_rate=random.choice(vat_rates)
        )
        db.session.add(n)
        nomenclatures.append(n)
        
    db.session.commit() 

    # 3. Створення 100 Документів
    doc_types = ["Замовлення", "Рахунок фактура", "Прибуткова накладна", "Видаткова накладна"]
    
    for i in range(1, 10):
        doc_id = str(uuid.uuid4())
        current_dt = datetime.now()
        
        doc_datetime = current_dt - timedelta(
            days=random.randint(0, 90),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59)
        )
        operation = random.choice(doc_types)
        counterparty = random.choice(counterparties)
        total_amount = round(random.uniform(500, 50000), 2)
        
        doc = Document(
            documents_id=doc_id,
            document_date=doc_datetime,
            operation_type=operation,
            total_amount=str(total_amount),
            currency="UAH",
            counterparty_id=counterparty.counterparty_id,
        )
        db.session.add(doc)
        
        # 4. Створення Рядків Документа
        num_lines = random.randint(1, 5)
        
        for j in range(num_lines):
            line_id = str(uuid.uuid4())
            nomenclature = random.choice(nomenclatures)
            qty = random.randint(1, 20)
            price = round(random.uniform(10, 500), 2)
            total = round(qty * price * 1.2, 2)
            
            line = DocumentLine(
                product_item_id=line_id,
                document_id=doc_id,
                nomenclature_id=nomenclature.nomenclature_id,
                quantity=str(qty),
                unit="шт" if "Товар" in nomenclature.nomenclature_name else "послуга",
                price_with_vat=str(price * 1.2),
                total_with_vat=str(total),
                vat_amount=str("20%"), 
                total_amount=str(total / 1.2),
            )
            db.session.add(line)

    db.session.commit()
    print("Створення тестових даних завершено!")