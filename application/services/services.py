from decimal import Decimal
from datetime import datetime
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from application import db
from application.models import Document, DocumentLine, InventoryBalance
from application.services.exceptions import PostingError, InsufficientStockError


class OperationType:
    """Константи для типів операцій, щоб уникнути магічних рядків."""
    INCOMING = ['Purchase', 'Incoming', 'Прибуткова накладна']
    OUTGOING = ['Sale', 'Outgoing', 'Видаткова накладна']

    @classmethod
    def get_modifier(cls, op_type: str) -> int:
        if op_type in cls.INCOMING:
            return 1
        if op_type in cls.OUTGOING:
            return -1
        raise PostingError(f"Невідомий тип операції: {op_type}")


class FifoCostCalculator:
    """
    Відповідає виключно за розрахунок собівартості списання (FIFO).
    Ізолює складну логіку запитів до історії партій.
    """
    def __init__(self, session):
        self.session = session

    def calculate_cost(self, document: Document, line: DocumentLine) -> Decimal:
        #  Скільки цього товару ми вже продали/списали раніше (до цього документа)
        # Це потрібно, щоб зрозуміти, які партії "вже з'їли" попередні продажі
        prev_sold_query = select(func.sum(DocumentLine.quantity)).join(Document).filter(
            Document.is_posted == True,
            Document.operation_type.in_(OperationType.OUTGOING),
            DocumentLine.nomenclature_id == line.nomenclature_id,
            (Document.document_date < document.document_date) |
            ((Document.document_date == document.document_date) & (Document.documents_id < document.documents_id))
        )
        total_sold_previously = self.session.execute(prev_sold_query).scalar() or 0

        # Отримуємо всі вхідні партії (приходи), відсортовані за часом (FIFO)
        incoming_batches = self.session.execute(
            select(DocumentLine).join(Document).filter(
                Document.is_posted == True,
                Document.operation_type.in_(OperationType.INCOMING),
                DocumentLine.nomenclature_id == line.nomenclature_id
            ).order_by(Document.document_date.asc(), Document.documents_id.asc())
        ).scalars().all()


        qty_to_write_off = float(line.quantity)
        fifo_cost = 0.0
        # Скільки товару з початку черги треба пропустити, бо він вже був проданий раніше
        items_to_skip = float(total_sold_previously)

        for batch in incoming_batches:
            if qty_to_write_off <= 0:
                break

            batch_qty = float(batch.quantity)
            # Розраховуємо ціну одиниці в цій конкретній партії
            batch_price = (float(batch.total_amount) / batch_qty) if batch_qty else 0

            # Якщо ця партія вже повністю вичерпана попередніми продажами
            if items_to_skip >= batch_qty:
                items_to_skip -= batch_qty
                continue

            # Скільки доступно в цій партії зараз
            available_in_batch = batch_qty - items_to_skip
            items_to_skip = 0  # Ми знайшли "живу" партію, далі пропускати не треба

            # Скільки беремо з цієї партії
            take = min(qty_to_write_off, available_in_batch)
            
            fifo_cost += take * batch_price
            qty_to_write_off -= take

        return Decimal(str(round(fifo_cost, 2)))


class InventoryManager:
    """
    Відповідає за безпосередню зміну стану складу (InventoryBalance).
    Приховує логіку пошуку або створення запису залишків.
    """
    def __init__(self, session):
        self.session = session

    def _get_or_create_balance(self, nomenclature_id: str, account: str) -> InventoryBalance:
        balance = self.session.execute(
            select(InventoryBalance).filter_by(
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
            self.session.add(balance)
        return balance

    def add_stock(self, line: DocumentLine):
        """Оприбуткування (кількість + сума з документа)"""
        balance = self._get_or_create_balance(line.nomenclature_id, line.account)
        balance.quantity += line.quantity
        balance.total_amount += line.total_amount
        balance.last_updated = datetime.now()

    def remove_stock(self, line: DocumentLine, cost_amount: Decimal):
        """Списання (кількість - розрахована собівартість)"""
        balance = self._get_or_create_balance(line.nomenclature_id, line.account)

        if balance.quantity < line.quantity:
            raise InsufficientStockError(
                f'Недостатньо товару "{line.nomenclature.nomenclature_name}". '
                f'На залишку: {balance.quantity}, Потрібно: {line.quantity}'
            )

        balance.quantity -= line.quantity
        balance.total_amount -= cost_amount
        balance.last_updated = datetime.now()


class DocumentPostingService:
    """
    Фасадний сервіс (Orchestrator).
    Він знає ЛИШЕ послідовність дій для проведення документа.
    """
    def __init__(self, db_session):
        self.db = db_session
        self.inventory_manager = InventoryManager(db_session)
        self.fifo_calculator = FifoCostCalculator(db_session)

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

        # Визначення напрямку руху (Прихід/Розхід)
        modifier = OperationType.get_modifier(document.operation_type)


        for line in document.lines:
            if modifier == 1:

                self.inventory_manager.add_stock(line)
            else:
                # Розхід: складний процес
                # А. Рахуємо собівартість
                cost_to_write_off = self.fifo_calculator.calculate_cost(document, line)
                
                # Б. Оновлюємо рядок документа (записуємо туди собівартість для історії)
                # Це важливо: ми зберігаємо розраховану собівартість у сам рядок продажу
                line.total_cost = cost_to_write_off 
                
                # В. Списуємо зі складу
                self.inventory_manager.remove_stock(line, cost_to_write_off)


        document.is_posted = True
        document.last_updated = datetime.now()
        self.db.commit()