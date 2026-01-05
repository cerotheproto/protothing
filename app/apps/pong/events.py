from dataclasses import dataclass
from models.app_contract import Event


@dataclass
class MovePlayer(Event):
    player_id: int  # 1 or 2
    direction: int  # -1 for up, 1 for down


@dataclass
class ResetGame(Event):
    pass
