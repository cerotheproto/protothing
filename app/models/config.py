# тут модели для config.yaml

from pydantic import BaseModel

class SystemConfig(BaseModel):
    transport: str = ""
    startup_app: str
    target_fps: int = 60
    ws_enabled: bool = False

class ReactiveFaceConfig(BaseModel):
    default_preset: str

class LedStripConfig(BaseModel):
    led_number: int
    
class VideoPlayerConfig(BaseModel):
    default_video: str | None = None