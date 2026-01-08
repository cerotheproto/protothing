from apps.base import BaseApp
from render.frame_description import FrameDescription
from utils.sprites import load_sprite

class BSODApp(BaseApp):
    name = "bsod"

    def render(self) -> FrameDescription:
        """Возвращает описание кадра с синим экраном смерти"""
        sprite = load_sprite("assets/bsod/bsod.png")
        return FrameDescription(layers=[sprite])
        
