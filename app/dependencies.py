# глобальные экземпляры основных компонентов приложения

from app_manager import AppManager
from config import Config
from effect_manager import EffectManager
from render.renderer import Renderer
from render.transition_engine import TransitionEngine
from transport.driver import Driver
from display_manager import DisplayManager

app_manager = AppManager()
config = Config()  # будет загружен из config.yaml при старте
driver = Driver()
renderer = Renderer()
effect_manager = EffectManager()
display_manager = DisplayManager()
transition_engine = TransitionEngine()