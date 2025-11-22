from sqlalchemy import func, case, select, literal_column
from application import db
from application.models import Document, DocumentLine, Counterparty, Nomenclature

class ReportService:
    def __init__(self, session):
        self.session = session

    def get_sales_report(self, start_date, end_date):
        """Звіт про продажі: показує виручку."""
        query = select(
            Document.document_date,
            Document.documents_id,
            Counterparty.counterparty_name,
            Nomenclature.nomenclature_name,
            DocumentLine.quantity,
            DocumentLine.total_amount  # Тут це ціна продажу (Виручка)
        ).join(DocumentLine.document)\
         .join(DocumentLine.nomenclature)\
         .join(Document.counterparty)\
         .filter(
            Document.is_posted == True,
            Document.operation_type == 'Видаткова накладна',
            Document.document_date.between(start_date, end_date)
        ).order_by(Document.document_date)

        return self.session.execute(query).all()

    def get_inventory_on_date(self, target_date):
        """
        Залишки на дату (Розрахунковий метод).
        УВАГА: Для коректної суми треба використовувати собівартість (total_cost) для списань.
        """
        INCOMING = ['Purchase', 'Incoming', 'Прибуткова накладна']
        OUTGOING = ['Sale', 'Outgoing', 'Видаткова накладна']

        
        outgoing_cost_column = DocumentLine.total_cost if hasattr(DocumentLine, 'total_cost') else DocumentLine.total_amount

        query = select(
            Nomenclature.nomenclature_name,
            #  Сальдо кількості (Прихід - Розхід)
            func.sum(case(
                (Document.operation_type.in_(INCOMING), DocumentLine.quantity),
                (Document.operation_type.in_(OUTGOING), -DocumentLine.quantity),
                else_=0
            )).label('balance_qty'),
            
            # Сальдо вартості (Прихідна вартість - Собівартість списання)
            func.sum(case(
                (Document.operation_type.in_(INCOMING), DocumentLine.total_amount), 
                (Document.operation_type.in_(OUTGOING), -outgoing_cost_column), 
                else_=0
            )).label('balance_sum')
        ).join(DocumentLine.document)\
         .join(DocumentLine.nomenclature)\
         .filter(
            Document.is_posted == True,
            Document.document_date <= target_date
        ).group_by(Nomenclature.nomenclature_id, Nomenclature.nomenclature_name)

        results = self.session.execute(query).all()
        
        # Фільтруємо нульові залишки 
        return [r for r in results if r.balance_qty != 0]