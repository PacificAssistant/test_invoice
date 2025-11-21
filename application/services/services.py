# application/services.py
from decimal import Decimal
from datetime import datetime
from sqlalchemy import func, and_
from application import db  # Використовуємо глобальний об'єкт db для побудови запитів (db.select)
from application.models import Document, DocumentLine, InventoryBalance

# Винятки
class PostingError(Exception):
    pass

class InsufficientStockError(PostingError):
    pass

class DocumentPostingService:
    INCOMING_TYPES = ['Purchase', 'Incoming', 'Прибуткова накладна']
    OUTGOING_TYPES = ['Sale', 'Outgoing', 'Видаткова накладна']

    def __init__(self, db_session):
        self.db = db_session # Це сесія для execute/commit

    def post_document(self, doc_id: str):

        document = self.db.execute(
            db.select(Document)
            .filter_by(documents_id=doc_id)
            .options(db.selectinload(Document.lines).selectinload(DocumentLine.nomenclature))
        ).scalar_one_or_none()

        if not document:
            raise PostingError("Документ не знайдено.")
        
        if document.is_posted:
            raise PostingError("Документ вже проведений!")

        modifier = self._get_modifier(document.operation_type)

        for line in document.lines:
            self._process_line(document, line, modifier)

        document.is_posted = True
        document.last_updated = datetime.now()
        self.db.commit()

    def _get_modifier(self, operation_type):
        if operation_type in self.INCOMING_TYPES:
            return 1
        elif operation_type in self.OUTGOING_TYPES:
            return -1
        else:
            raise PostingError(f"Невідомий тип операції: {operation_type}")

    def _get_or_create_balance(self, nomenclature_id, account):

        balance = self.db.execute(
            db.select(InventoryBalance).filter_by(
                nomenclature_id=nomenclature_id,
                account=account
            )
        ).scalar_one_or_none()

        if not balance:
            balance = InventoryBalance(
                nomenclature_id=nomenclature_id,
                account=account,
                quantity=0,
                total_amount=0
            )
            self.db.add(balance)
        return balance

    def _process_line(self, document, line, modifier):
        balance = self._get_or_create_balance(line.nomenclature_id, line.account)

        if modifier == 1: # Прихід
            balance.quantity += line.quantity
            balance.total_amount += line.total_amount
        
        elif modifier == -1: # Розхід
            if balance.quantity < line.quantity:
                raise InsufficientStockError(
                    f'Недостатньо товару "{line.nomenclature.nomenclature_name}". '
                    f'Є: {balance.quantity}, Треба: {line.quantity}'
                )
            
            cost_to_write_off = self._calculate_fifo_cost(document, line)
            
            balance.quantity -= line.quantity

            balance.total_amount -= Decimal(str(round(cost_to_write_off, 2)))

    def _calculate_fifo_cost(self, current_doc, line) -> float:

        prev_sold_query = db.select(func.sum(DocumentLine.quantity)).join(Document).filter(
            Document.is_posted == True,
            Document.operation_type.in_(self.OUTGOING_TYPES),
            DocumentLine.nomenclature_id == line.nomenclature_id,
            (Document.document_date < current_doc.document_date) | 
            ((Document.document_date == current_doc.document_date) & (Document.documents_id < current_doc.documents_id))
        )
        total_sold_previously = self.db.execute(prev_sold_query).scalar() or 0

        incoming_batches = self.db.execute(
            db.select(DocumentLine).join(Document).filter(
                Document.is_posted == True,
                Document.operation_type.in_(self.INCOMING_TYPES),
                DocumentLine.nomenclature_id == line.nomenclature_id
            ).order_by(Document.document_date.asc(), Document.documents_id.asc())
        ).scalars().all()

        qty_to_write_off = float(line.quantity)
        fifo_cost = 0.0
        items_to_skip = float(total_sold_previously)

        for batch in incoming_batches:
            if qty_to_write_off <= 0:
                break
            
            batch_qty = float(batch.quantity)
            batch_price = (float(batch.total_amount) / batch_qty) if batch_qty else 0

            if items_to_skip >= batch_qty:
                items_to_skip -= batch_qty
                continue
            
            available_in_batch = batch_qty - items_to_skip
            items_to_skip = 0 
            
            take = min(qty_to_write_off, available_in_batch)
            fifo_cost += take * batch_price
            qty_to_write_off -= take
            
        return fifo_cost