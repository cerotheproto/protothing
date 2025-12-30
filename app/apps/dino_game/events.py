from models.app_contract import Event

class JumpEvent(Event):
    """Заставляет динозаврика прыгнуть"""
    pass

class DuckEvent(Event):
    """Переключает состояние приседания (тогл)"""
    pass

class RestartEvent(Event):
    """Перезапуск игры"""
    pass
