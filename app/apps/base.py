# apps/base_app.py
import logging
from models.app_contract import Event, Query, QueryResult
from typing import Optional
from render.frame_description import FrameDescription
from render.frame import Frame

logger = logging.getLogger(__name__)
class BaseApp:
    name: str = "unnamed"   # unique name of the application

    def __init__(self):
      pass  

    def start(self):
        "Called when the application starts"
        logger.info(f"Starting application: {self.name}")

    def stop(self):
        "Called when the application stops"
        logger.info(f"Stopping application: {self.name}")
        
    # обновление состояния, события приходят через events
    def update(self, dt: float, events: list[Event]):
        "Update the state, events come through events parameter"
        pass

    # возвращает Frame или FrameDescription
    def render(self) -> Optional[FrameDescription | Frame]:
        "Renders the current frame or frame description"
        return None

    # список типов запросов, которые приложение может обрабатывать
    def get_queries(self) -> list[type[Query]]:
        "Returns a list of query types that the application can handle"
        return []
    
    # список типов событий, которые приложение может обрабатывать
    def get_events(self) -> list[type[Event]]:
        "Returns a list of event types that the application can handle"
        return []
    
    # обработка запроса
    def handle_query(self, query: Query) -> QueryResult:
        "Handles a query and returns the result"
        raise NotImplementedError(f"Query {type(query).__name__} is not supported")
