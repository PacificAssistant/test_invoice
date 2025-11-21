from sqlalchemy import String, Integer, Date, ForeignKey, DateTime, Numeric, Boolean
from sqlalchemy.orm import relationship, Mapped, mapped_column 

from typing import List, Optional 
from datetime import date, datetime

from application import db 


class Counterparty(db.Model):
    __tablename__ = 'counterparty'
    

    counterparty_id: Mapped[str] = mapped_column(String, primary_key=True)
    counterparty_name: Mapped[str] = mapped_column(String, nullable=False)
    

    documents: Mapped[List["Document"]] = relationship(back_populates="counterparty", lazy=True)

    def __repr__(self):
        return f'<Counterparty {self.counterparty_name}>'



class Document(db.Model):
    __tablename__ = 'documents'
    
    documents_id: Mapped[str] = mapped_column(String, primary_key=True)
    document_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
   
    operation_type: Mapped[Optional[str]] = mapped_column(String)
    total_amount: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    currency: Mapped[Optional[str]] = mapped_column(String)
    incoming_date: Mapped[Optional[str]] = mapped_column(String)
    incoming_number: Mapped[Optional[str]] = mapped_column(String)
    contract_name: Mapped[Optional[str]] = mapped_column(String)
    
    counterparty_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey(Counterparty.counterparty_id, onupdate='CASCADE', ondelete='RESTRICT'),
        nullable=True
    )
    
    is_posted: Mapped[bool] = mapped_column(Boolean, default=False)

    counterparty: Mapped["Counterparty"] = relationship(back_populates="documents")
    

    lines: Mapped[List["DocumentLine"]] = relationship(back_populates="document", lazy=True)

    def __repr__(self):
        return f'<Document {self.documents_id} ({self.document_date})>'



class Nomenclature(db.Model):
    __tablename__ = 'nomenclature'
    
    nomenclature_id: Mapped[str] = mapped_column(String, primary_key=True)
    nomenclature_name: Mapped[str] = mapped_column(String, nullable=False)

    vat_rate: Mapped[Optional[str]] = mapped_column(String, nullable=True) 
    
    document_lines: Mapped[List["DocumentLine"]] = relationship(back_populates="nomenclature", lazy=True)

    def __repr__(self):
        return f'<Nomenclature {self.nomenclature_name}>'
    

    
class DocumentLine(db.Model):
    __tablename__ = 'document_lines'
    
    product_item_id: Mapped[str] = mapped_column(String, primary_key=True)
    

    quantity: Mapped[Optional[float]] = mapped_column(Numeric(12))
    price_with_vat: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    total_with_vat: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    vat_amount: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    total_amount: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    total_cost: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), default=0)

    account: Mapped[Optional[str]] = mapped_column(String)
    unit: Mapped[Optional[str]] = mapped_column(String)
    

    document_id: Mapped[str] = mapped_column(
        ForeignKey(Document.documents_id, onupdate='CASCADE', ondelete='RESTRICT'),
        nullable=False
    )
    nomenclature_id: Mapped[str] = mapped_column(
        ForeignKey(Nomenclature.nomenclature_id, onupdate='CASCADE', ondelete='RESTRICT'),
        nullable=False
    )
    

    document: Mapped["Document"] = relationship(back_populates="lines")
    nomenclature: Mapped["Nomenclature"] = relationship(back_populates="document_lines")


    def __repr__(self):
        return f'<DocumentLine {self.product_item_id}>'
    


class InventoryBalance(db.Model):
    __tablename__ = 'inventory_balances'

    # Унікальний ID запису залишку
    balance_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Зв'язок з номенклатурою (обов'язково)
    nomenclature_id: Mapped[str] = mapped_column(
        ForeignKey(Nomenclature.nomenclature_id, onupdate='CASCADE', ondelete='RESTRICT'),
        nullable=False
    )

    # Залишки часто зберігаються в розрізі бухгалтерського рахунку (якщо він у вас є в DocumentLine)
    account: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Кількісний залишок
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), default=0)

    # Сумовий залишок (вартість товару на складі)
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    # Поле для відстеження останнього оновлення (корисно для аудиту)
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)

    # Зв'язок (Relationship) для зручного доступу до назви товару
    nomenclature: Mapped["Nomenclature"] = relationship(lazy="joined")

    # Унікальний індекс: один товар на одному рахунку не може мати два рядки залишків
    __table_args__ = (
        db.UniqueConstraint('nomenclature_id', 'account', name='uix_nomenclature_account'),
    )

    def __repr__(self):
        return f'<Balance {self.nomenclature.nomenclature_name}: {self.quantity}>'

