# apps/base_app.py
from models.app_contract import Event, Query, QueryResult
from typing import Optional
from render.frame_description import FrameDescription
from render.frame import Frame
class BaseApp:
    name: str = "unnamed"   # уникальное имя приложения

    def __init__(self):
      pass  

    # вызывается, когда приложение становится активным
    def start(self):
        print(f"Запуск приложения: {self.name}")

    # вызывается, когда приложение выключается
    def stop(self):
        print(f"Остановка приложения: {self.name}")
        
    # обновление состояния, события приходят через events
    def update(self, dt: float, events: list[Event]):
        pass

    # возвращает Frame или FrameDescription
    def render(self) -> Optional[FrameDescription | Frame]:
        return None

    # список типов запросов, которые приложение может обрабатывать
    def get_queries(self) -> list[type[Query]]:
        return []
    
    # список типов событий, которые приложение может обрабатывать
    def get_events(self) -> list[type[Event]]:
        return []
    
    # обработка запроса
    def handle_query(self, query: Query) -> QueryResult:
        raise NotImplementedError(f"Запрос {type(query).__name__} не поддерживается")
