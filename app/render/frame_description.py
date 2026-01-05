from dataclasses import dataclass, field
from typing import Callable
import numpy as np

# ------ базовые классы для слоев и эффектов ------
@dataclass
class Layer:
    pass # базовый класс для слоев

@dataclass
class Effect:
    id: str = field(default="", init=False)  # уникальный ID эффекта
    
    def cleanup(self, layers: list) -> None:
        """Очищает состояние эффекта и восстанавливает исходные позиции"""
        pass

# ------ типы слоёв ------
@dataclass
class FillLayer(Layer):
    color: tuple[int, int, int, int] 

@dataclass
class SpriteLayer(Layer):
    image: bytes  # RGBA данные изображения (4 байта на пиксель)
    sprite_width: int
    sprite_height: int
    x: float = 0.0  # позиция на экране
    y: float = 0.0

@dataclass
class AnimatedSpriteLayer(Layer):
    frames: list[bytes]  # список RGBA данных для каждого фрейма
    frame_durations: list[float]  # длительность каждого фрейма в секундах
    sprite_width: int
    sprite_height: int
    x: float = 0.0
    y: float = 0.0
    current_frame: int = 0
    elapsed_time: float = 0.0
    loop: bool = True  # автоматическое зацикливание
    on_complete: Callable[[], None] | None = None  # callback при завершении анимации
    _previous_frame: int = 0  # для отслеживания смены фрейма (пинг-понг и другие режимы)
    _completed_once: bool = False  # флаг для отслеживания завершения один раз

@dataclass
class TextLayer(Layer):
    text: str
    x: float = 0.0
    y: float = 0.0
    font_size: int = 12
    color: tuple[int, int, int, int] = (255, 255, 255, 255)  # RGBA
    font_path: str | None = None  # путь к TTF шрифту, если None - используется дефолтный

@dataclass
class RectLayer(Layer):
    x: float
    y: float
    width: float
    height: float
    color: tuple[int, int, int, int]  # RGBA

# ------ типы эффектов ------

@dataclass
class WiggleEffect(Effect):
    amplitude: float = 2.0  # максимальный сдвиг в пикселях
    min_interval: float = 0.35  # минимальная длительность плавного смещения
    max_interval: float = 0.85  # максимальная длительность смещения
    lateral_ratio: float = 0.45  # относительная амплитуда перпендикулярной компоненты
    direction_interval_min: float = 1.2  # базовый промежуток смены общего направления
    direction_interval_max: float = 2.6
    seed: int | None = None
    _direction: np.ndarray | None = field(default=None, repr=False)
    _direction_target: np.ndarray | None = field(default=None, repr=False)
    _direction_elapsed: float = field(default=0.0, repr=False)
    _direction_duration: float = field(default=1.0, repr=False)
    
    # Global wiggle state
    _current_offset: np.ndarray = field(default_factory=lambda: np.zeros(2, dtype=np.float32), repr=False)
    _target_offset: np.ndarray = field(default_factory=lambda: np.zeros(2, dtype=np.float32), repr=False)
    _start_offset: np.ndarray = field(default_factory=lambda: np.zeros(2, dtype=np.float32), repr=False)
    _offset_elapsed: float = field(default=0.0, repr=False)
    _offset_duration: float = field(default=1.0, repr=False)
    
    _sprite_states: dict[int, dict] = field(default_factory=dict, repr=False)
    _rng_state: np.random.Generator | None = field(default=None, repr=False)
    
    def cleanup(self, layers: list) -> None:
        """Восстанавливает исходные позиции спрайтов"""
        from render.effects.wiggle import cleanup_wiggle_effect
        cleanup_wiggle_effect(self, layers)


@dataclass
class DizzyEffect(Effect):
    amplitude: float = 0.8  # амплитуда смещения в пикселях (субпиксельная)
    speed: float = 0.5  # скорость волны (циклы в секунду)
    wave_scale: float = 2.0  # масштаб волны (сколько волн на экран)
    vertical_ratio: float = 0.7  # соотношение вертикального смещения к горизонтальному
    _phase: float = field(default=0.0, repr=False)


@dataclass
class ShakeEffect(Effect):
    amplitude: float = 2.0  # максимальный сдвиг в пикселях
    frequency: float = 10.0  # частота тряски (смены направления в секунду)
    seed: int | None = None
    _rng_state: np.random.Generator | None = field(default=None, repr=False)
    _shake_offset: np.ndarray = field(default_factory=lambda: np.zeros(2, dtype=np.float32), repr=False)


@dataclass
class RainbowEffect(Effect):
    speed: float = 1.0  # скорость переливания (циклы в секунду)
    use_position: bool = True  # если True, цвет зависит от позиции пикселя, если False - одинаков для всех
    fade_in_duration: float = 1.0
    fade_out_duration: float = 1.0
    _phase: float = field(default=0.0, repr=False)
    _state: str = field(default='fade_in', repr=False) # fade_in, running, fade_out, finished
    _fade_progress: float = field(default=0.0, repr=False)
    _is_stopping: bool = field(default=False, repr=False)


@dataclass
class ColorOverrideEffect(Effect):
    base_color: tuple[int, int, int] = (255, 255, 255)  # основной цвет для переопределения
    glare_enabled: bool = True  # включить эффект блика
    glare_color: tuple[int, int, int] = (255, 255, 255)  # цвет блика
    glare_intensity: float = 0.6  # интенсивность блика (0.0-1.0)
    glare_count: int = 3  # количество бликов на экране
    seed: int | None = None  # seed для рандомизации позиций бликов
    _glare_phase: float = field(default=0.0, repr=False)
    _glare_positions: list | None = field(default=None, repr=False)
    _rng_state: np.random.Generator | None = field(default=None, repr=False)

# ------ описание кадра ------
@dataclass
class FrameDescription:
    width: int = 64
    height: int = 32
    layers: list[Layer] = field(default_factory=list)
    effects: list[Effect] = field(default_factory=list)

