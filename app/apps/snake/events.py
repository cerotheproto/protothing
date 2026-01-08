from models.app_contract import Event


class MoveSnake(Event):
    direction: int  # 0 - up, 1 - down, 2 - left, 3 - right


class ResetSnakeGame(Event):
    pass
