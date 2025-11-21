
class PostingError(Exception):
    """Базовий клас для помилок проведення."""
    pass

class InsufficientStockError(PostingError):
    """Помилка недостатньої кількості товару."""
    pass