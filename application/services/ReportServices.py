from sqlalchemy import func, case, select, literal_column
from application import db
from application.models import Document, DocumentLine, Counterparty, Nomenclature
from datetime import datetime

class ReportService:
    def __init__(self, session):
        self.session = session

    def get_sales_report(self, start_date, end_date):
        """Звіт про продажі: виправлена версія з налагодженням."""
        
        query = select(
            Document.document_date,
            Document.document_number,
            func.coalesce(Counterparty.counterparty_name, "Роздрібний покупець").label('counterparty_name'),
            Nomenclature.nomenclature_name,
            DocumentLine.quantity,
            DocumentLine.total_amount
        ).select_from(DocumentLine) \
         .join(Document) \
         .join(Nomenclature) \
         .outerjoin(Counterparty, Document.counterparty_id == Counterparty.counterparty_id) \
         .filter(
            Document.is_posted == True, 
            Document.operation_type == 'Видаткова накладна',
            Document.document_date >= start_date,  
            Document.document_date <= end_date
        ).order_by(Document.document_date)

        results = self.session.execute(query).all()
        
        return results

    def get_inventory_on_date(self, target_date):
        """
        Залишки на дату (Розрахунковий метод).
        """

        INCOMING = ['Purchase', 'Incoming', 'Прибуткова накладна']
        OUTGOING = ['Sale', 'Outgoing', 'Видаткова накладна']

        outgoing_cost_column = DocumentLine.total_cost if hasattr(DocumentLine, 'total_cost') else DocumentLine.total_amount

        query = select(
            Nomenclature.nomenclature_name,
            # Сальдо кількості
            func.sum(case(
                (Document.operation_type.in_(INCOMING), DocumentLine.quantity),
                (Document.operation_type.in_(OUTGOING), -DocumentLine.quantity),
                else_=0
            )).label('balance_qty'),
            
            # Сальдо вартості
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
        
        return [r for r in results if r.balance_qty != 0]