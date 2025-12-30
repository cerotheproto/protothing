from models.app_contract import Event, Query, QueryResult
from pydantic import BaseModel
from typing import Optional, List

class Launch(Event):
    command: str
    args: List[str] = []

class Close(Event):
    pass

class UpdateGeometry(Event):
    x: int
    y: int
    width: int
    height: int

class Status(Query):
    pass

class RefreshWindow(Event):
    """Обновить геометрию окна из xdotool"""
    pass

class StatusResult(QueryResult):
    running: bool
    command: Optional[str] = None
    geometry: Optional[dict] = None

