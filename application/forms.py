from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, FloatField, DateField, FieldList, FormField, HiddenField, Form
from wtforms.validators import DataRequired, InputRequired, NumberRange, ValidationError
from datetime import date
from decimal import Decimal 
from dataclasses import dataclass


class DocumentLineForm(Form): 

    nomenclature_id = HiddenField('Номенклатура ID', validators=[DataRequired()])
    
    quantity = FloatField('Кількість', validators=[
        InputRequired(), 
        NumberRange(min=0.001, message='Кількість має бути більше 0.')
    ])
    vat_rate = FloatField('ПДВ %', default=20.0, validators=[
        InputRequired(),
        NumberRange(min=0, max=100, message='ПДВ має бути від 0% до 100%')
    ])

    price_with_vat = FloatField('Ціна з ПДВ', validators=[
        InputRequired(), 
        NumberRange(min=0.01)
    ])
    



class DocumentForm(FlaskForm):
    # Список типів 
    DOC_TYPES = ["Замовлення", "Рахунок фактура", "Прибуткова накладна", "Видаткова накладна","Податкова накладна"]

    document_date = DateField('Дата Документа', format='%d-%m-%Y', default=date.today,
                               validators=[DataRequired()])
    
    operation_type = SelectField(
        'Тип Операції', 
        choices=[('', 'Оберіть тип')] + [(t, t) for t in DOC_TYPES], # Генеруємо (Value, Label) однаковими
        validators=[DataRequired()]
    )
    
    counterparty_id = SelectField('Контрагент', choices=[('', 'Оберіть контрагента')],
                                   validators=[DataRequired()])

    lines = FieldList(FormField(DocumentLineForm), min_entries=1)

    def validate_lines(form, field):
        if not field.entries:
            raise ValidationError('Документ повинен містити хоча б один рядок.')
        

class ReportForm(FlaskForm):
    start_date = DateField('З дати', format='%d-%m-%Y', default=date.today, validators=[DataRequired()])
    end_date = DateField('По дату', format='%d-%m-%Y', default=date.today, validators=[DataRequired()])
    report_type = SelectField('Тип звіту', choices=[
        ('sales', 'Звіт про продажі'),
        ('inventory_date', 'Залишки на дату'),

    ])


        
