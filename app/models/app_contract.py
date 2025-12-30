# Базовые классы для системы событий и запросов приложений
from pydantic import BaseModel


class Event(BaseModel):
    """Базовый класс события - любое входящее воздействие на приложение"""
    pass


class Query(BaseModel):
    """Базовый класс запроса - получает состояние приложения"""
    pass


class QueryResult(BaseModel):
    """Базовый класс результата запроса"""
    pass
