from pydantic import BaseModel
import yaml
from models.config import SystemConfig, ReactiveFaceConfig, LedStripConfig, VideoPlayerConfig, WebUIConfig

class GlobalConfig(BaseModel):
    system: SystemConfig
    reactive_face: ReactiveFaceConfig
    led_strip: LedStripConfig
    video_player: VideoPlayerConfig
    webui: WebUIConfig

class Config:
    def __init__(self, path: str = "config.yaml"):
        self.path = path
        self.model = None

    def load(self):
        data = yaml.safe_load(open(self.path, "r", encoding="utf-8"))
        self.model = GlobalConfig(**data)
        return self.model
    
    def get(self) -> GlobalConfig:
        if self.model is None:
            return self.load()
        return self.model
    
    