
import uuid
from datetime import datetime
from application import db
from application.models import Document, DocumentLine
from application.services.services import SequenceConfig
from sqlalchemy import text

class DocumentService:
    
    @staticmethod
    def get_next_number(operation_type):
        """
        Генерує наступний номер документа на основі типу операції
        використовуючи SQL Sequence defined in SequenceConfig.
        """
        sequence_name = SequenceConfig.get_sequence_name(operation_type)
        try:
            # Виконуємо запит до Sequence
            result = db.session.execute(text(f"SELECT nextval('{sequence_name}')"))
            next_number = result.scalar_one()
            return next_number
        except Exception as e:
            print(f"Error generating sequence for {operation_type}: {e}")
            return None

    @staticmethod
    def calculate_line_amounts(quantity, price_without_vat, vat_rate_percent=20.0):
        """
        Розрахунок сум рядка (ПДВ, без ПДВ тощо).
        """
        if not vat_rate_percent:
            vat_rate_percent = 0.0
            
        vat_coefficient = float(vat_rate_percent) / 100.0
        vat_multiplier = 1 + vat_coefficient
        
        # Захист від ділення на нуль, якщо ціна 0
        price_with_vat = price_without_vat * vat_multiplier if vat_multiplier else price_with_vat
        total_with_vat = quantity * price_with_vat
        total_without_vat = quantity * price_without_vat
        vat_amount = total_with_vat - total_without_vat
        
        return {
            'price_without_vat': price_without_vat,
            'total_without_vat': total_without_vat,
            'total_with_vat': total_with_vat,
            'vat_amount': vat_amount,
        }

