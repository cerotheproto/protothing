from pydantic import BaseModel
from models.app_contract import Event


class Flap(Event):
    """Bird flap event"""
    pass


class ResetFlappyBirdGame(Event):
    """Reset game state"""
    pass
