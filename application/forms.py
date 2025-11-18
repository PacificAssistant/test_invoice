from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, FloatField, DateField, FieldList, FormField, HiddenField
from wtforms.validators import DataRequired, InputRequired, NumberRange, ValidationError
from datetime import date
from decimal import Decimal # Рекомендується для фінансових розрахунків

# Допоміжний клас форми для одного рядка документа (таблична частина)
class DocumentLineForm(FlaskForm):
    # HiddenField для ID номенклатури (значення з SelectField)
    nomenclature_id = HiddenField('Номенклатура ID', validators=[DataRequired()])
    
    # Використовуємо StringField для відображення назви (якщо потрібно)
    # Або просто використовуємо SelectField у шаблоні, а тут лише приймаємо ID
    # nomenclature_name = StringField('Номенклатура') 
    
    # Використовуємо FloatField для числових значень
    quantity = FloatField('Кількість', validators=[
        InputRequired(), 
        NumberRange(min=0.01, message='Кількість має бути більше 0.')
    ])
    price_with_vat = FloatField('Ціна з ПДВ', validators=[
        InputRequired(), 
        NumberRange(min=0.01, message='Ціна має бути більше 0.')
    ])
    
    # Тут можна додати інші поля, якщо вони є (наприклад, одиниця виміру)


# Основний клас форми для документа
class DocumentForm(FlaskForm):
    # Поля заголовка
    document_date = DateField('Дата Документа', format='%Y-%m-%d', default=date.today, validators=[DataRequired()])
    
    # Зауваження: choices для SelectField потрібно буде завантажувати у роуті
    operation_type = SelectField('Тип Операції', choices=[
        ('', 'Оберіть тип'),
        ('income', 'Надходження'),
        ('outcome', 'Витрата')
    ], validators=[DataRequired()])
    
    counterparty_id = SelectField('Контрагент', choices=[('', 'Оберіть контрагента')], validators=[DataRequired()])
    
    # Поле для табличної частини: FieldList дозволяє обробляти список форм
    # min_entries=1 гарантує, що буде хоча б один рядок
    lines = FieldList(FormField(DocumentLineForm), min_entries=1)
    
    def validate_lines(form, field):
        """Перевірка, чи всі необхідні поля в рядках заповнені."""
        if not field.entries:
            raise ValidationError('Документ повинен містити хоча б один рядок.')