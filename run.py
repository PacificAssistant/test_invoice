from application import app , db
from application.models import Counterparty, Nomenclature, Document, DocumentLine 

from application.test.test_data_generator import create_test_data

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("База даних та всі 4 таблиці створені!")

        create_test_data()
        
        # ... тут може бути код для додавання тестових даних ...
        
    app.run(debug=True)
