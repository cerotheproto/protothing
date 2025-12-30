from apps.base import BaseApp
from models.app_contract import Event
from render.frame_description import FrameDescription

class SetTextEvent(Event):
    new_text: str


class TextTestApp(BaseApp):
    def __init__(self):
        super().__init__()
        self.name = "text_test"

    def update(self, dt, events):
        for event in events:
            if isinstance(event, SetTextEvent):
                self.current_text = event.new_text
    
    def render(self) -> FrameDescription:
        from render.frame_description import FrameDescription, TextLayer

        frame_desc = FrameDescription()
        text_layer = TextLayer(
            text=self.current_text if hasattr(self, 'current_text') else "тест",
            x=0,
            y=10,
            color=(255, 255, 255, 255),
            font_size=6
)
        frame_desc.layers.append(text_layer)
        return frame_desc
    
    def get_events(self) -> list[type[Event]]:
        return [SetTextEvent]

