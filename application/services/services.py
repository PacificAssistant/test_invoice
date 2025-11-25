from decimal import Decimal
from datetime import datetime
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from abc import ABC, abstractmethod
from dataclasses import dataclass

from application import db
from application.models import Document, DocumentLine, InventoryBalance
from application.services.exceptions import PostingError, InsufficientStockError


from abc import ABC, abstractmethod
from application.models import Document, DocumentLine
from application.services.exceptions import PostingError


class BaseDocumentStrategy(ABC):
    def __init__(self, db_session, inventory_manager):
        self.db = db_session
        self.inventory = inventory_manager

    @abstractmethod
    def post(self, document: Document):
        """Логіка проведення"""
        pass

    @property
    def title(self):
        return "Документ"

    @property
    def next_document_type(self):
        """Повертає тип документа, який можна створити на підставі цього"""
        return None

# --- Стратегії для кожного типу ---

class OrderStrategy(BaseDocumentStrategy):
    @property
    def title(self):
        return "Замовлення"

    @property
    def next_document_type(self):
        return "Рахунок фактура"  # 1. Замовлення -> Рахунок

    def post(self, document: Document):
        # Замовлення не впливає на склад
        pass

class InvoiceStrategy(BaseDocumentStrategy):
    @property
    def title(self):
        return "Рахунок фактура"

    @property
    def next_document_type(self):
        return "Видаткова накладна"  # 2. Рахунок -> Видаткова

    def post(self, document: Document):
        pass

class OutgoingStrategy(BaseDocumentStrategy):
    @property
    def title(self):
        return "Видаткова накладна"
    
    @property
    def next_document_type(self):
        return "Податкова накладна"  # 3. Видаткова -> Податкова

    def post(self, document: Document):
        # Логіка списання зі складу (FIFO)
        for line in document.lines:
            cost = self.inventory.remove_stock_fifo(line)
            line.total_cost = round(cost, 2)

class IncomingStrategy(BaseDocumentStrategy):
    @property
    def title(self):
        return "Прибуткова накладна"

    def post(self, document: Document):
        # Логіка оприбуткування
        for line in document.lines:
            self.inventory.add_stock(document, line)

class TaxInvoiceStrategy(BaseDocumentStrategy):
    @property
    def title(self):
        return "Податкова накладна"

    def post(self, document: Document):
        pass


class DocumentStrategyFactory:
    _STRATEGIES = {
        'Замовлення': OrderStrategy,
        'Рахунок фактура': InvoiceStrategy,
        'Видаткова накладна': OutgoingStrategy,
        'Прибуткова накладна': IncomingStrategy,
        'Податкова накладна': TaxInvoiceStrategy
    }

    @classmethod
    def get_strategy(cls, doc_type, session, inventory_mgr):
        strategy_cls = cls._STRATEGIES.get(doc_type)
        if not strategy_cls:
            # Fallback або помилка
            return BaseDocumentStrategy(session, inventory_mgr) 
        return strategy_cls(session, inventory_mgr)






class InventoryManager:
    def __init__(self, session):
        self.session = session

    def add_stock(self, document: Document, line: DocumentLine):
        """
        Створення партії (Batch).
        """
        
        qty = Decimal(str(line.quantity))
        total = Decimal(str(line.total_amount))
        
        unit_cost = total / qty if qty > 0 else Decimal(0)
        document_date_only = document.document_date
        full_batch_datetime = datetime.combine(document_date_only, datetime.now().time())

        new_batch = InventoryBalance(
            nomenclature_id=line.nomenclature_id,
            incoming_line_id=line.product_item_id,
            account=line.account,
            batch_date=full_batch_datetime,
            quantity=qty,        
            unit_cost=unit_cost  
        )
        self.session.add(new_batch)

    def remove_stock_fifo(self, line: DocumentLine) -> Decimal:
        """
        Списання по FIFO.
        """
        qty_needed = Decimal(str(line.quantity))
        total_cost_written_off = Decimal(0)
        
        
        batches = self.session.execute(
            select(InventoryBalance)
            .filter(
                InventoryBalance.nomenclature_id == line.nomenclature_id,
                InventoryBalance.quantity > 0
            )
            .order_by(InventoryBalance.batch_date.asc(), InventoryBalance.balance_id.asc())
            .options(selectinload(InventoryBalance.nomenclature)) 
            .with_for_update()
        ).scalars().all()

        total_available = sum(b.quantity for b in batches)
        

        if total_available < qty_needed:
             raise InsufficientStockError(
                f'Недостатньо товару "{line.nomenclature.nomenclature_name}". '
                f'Доступно: {total_available}, Потрібно: {qty_needed}'
            )

        for batch in batches:
            if qty_needed <= 0:
                break


            available_in_batch = batch.quantity 
            
            if available_in_batch <= qty_needed:
                take_qty = available_in_batch
                batch.quantity = Decimal(0) 
            else:
                take_qty = qty_needed
                batch.quantity -= take_qty 

            cost_chunk = take_qty * batch.unit_cost
            total_cost_written_off += cost_chunk
            
            qty_needed -= take_qty

        return total_cost_written_off

class DocumentPostingService:
    def __init__(self, db_session):
        self.db = db_session
        self.inventory_manager = InventoryManager(db_session) 
    def post_document(self, doc_id: str):
        
        document = self.db.execute(
            select(Document)
            .filter_by(documents_id=doc_id)
            .options(selectinload(Document.lines).selectinload(DocumentLine.nomenclature))
        ).scalar_one_or_none()

        if not document:
            raise PostingError("Документ не знайдено.")
        
        if document.is_posted:
            raise PostingError("Документ вже проведений!")

        
        strategy = DocumentStrategyFactory.get_strategy(
            document.operation_type, 
            self.db, 
            self.inventory_manager
        )

        strategy.post(document)

       
        document.is_posted = True
        document.last_updated = datetime.now()
        self.db.commit()


@dataclass(frozen=True) # frozen=True робить його незмінним, як константа
class SequenceConfig:
    """Мапінг типу документа на назву послідовності для нумерації."""
    MAPPING = {
        "Замовлення": "doc_order_seq",
        "Рахунок фактура": "doc_invoice_seq",
        "Прибуткова накладна": "doc_incoming_seq",
        "Видаткова накладна": "doc_outgoing_seq",
        "Податкова накладна": "doc_tax_invoice_seq",
    }
    
    @classmethod
    def get_sequence_name(cls, operation_type: str) -> str:
        """Повертає назву послідовності за типом операції."""
        return cls.MAPPING.get(operation_type, "doc_default_seq")
