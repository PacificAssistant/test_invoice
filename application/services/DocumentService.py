# application/services.py
import uuid
from datetime import datetime
from application import db
from application.models import Document, DocumentLine

class DocumentService:
    
    @staticmethod
    def calculate_line_amounts(quantity, price_with_vat):
        """Розрахунок сум (ПДВ, без ПДВ) для одного рядка."""
        VAT_RATE = 0.20
        VAT_MULTIPLIER = 1 + VAT_RATE
        
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

    @staticmethod
    def create_document_from_form(form, operation_type, contract_name):
        try:

            
            doc_date = datetime.combine(form.document_date.data, datetime.now().time())
            
            new_document = Document(
                document_date=doc_date,
                operation_type=operation_type,
                total_amount=0, 
                currency="UAH",
                counterparty_id=form.counterparty_id.data,
                contract_name=contract_name
            )
            db.session.add(new_document)
            db.session.flush() 

            generated_id = new_document.documents_id
            total_doc_amount_without_vat = 0.0
            

            for line_form in form.lines.entries:
                quantity = float(line_form.data['quantity'])
                price_with_vat = float(line_form.data['price_with_vat'])
                nomenclature_id = line_form.data['nomenclature_id']
                
                amounts = DocumentService.calculate_line_amounts(quantity, price_with_vat)
                total_doc_amount_without_vat += amounts['total_without_vat']
                
                new_line = DocumentLine(
                    product_item_id=str(uuid.uuid4()),
                    document_id=generated_id, #  Integer ID
                    nomenclature_id=nomenclature_id,
                    quantity=quantity,
                    unit="шт.", 
                    price_with_vat=round(price_with_vat, 2),
                    total_with_vat=round(amounts['total_with_vat'], 2),
                    vat_amount=round(amounts['vat_amount'], 2), 
                    total_amount=round(amounts['total_without_vat'], 2),
                )
                db.session.add(new_line)

            new_document.total_amount = round(total_doc_amount_without_vat, 2)
            db.session.commit()
            
            return generated_id
            
        except Exception as e:
            db.session.rollback()
            raise e