"""
Глобальный движок переходов между кадрами/приложениями.
Обрабатывает переходы на уровне итоговых кадров.
"""

from dataclasses import dataclass, field
from enum import Enum
from render.frame import Frame
from utils.transition import (
    InterpolationMethod, AnimatedParameter, 
    calculate_image_similarity, lerp_array, cosine_interpolation,
    is_bright_to_dark
)
import numpy as np


# порог схожести для выбора типа перехода
SIMILARITY_THRESHOLD = 0.08


class TransitionType(Enum):
    """Типы переходов между кадрами"""
    NONE = "none"           # без перехода
    CROSSFADE = "crossfade"  # плавное затухание/появление
    MORPH = "morph"          # попиксельный морфинг
    JUMP = "jump"            # прыжок новой картинки снизу вверх


@dataclass
class FrameTransition:
    """Переход между двумя кадрами"""
    from_frame: Frame | None
    to_frame: Frame
    transition_type: TransitionType
    progress: AnimatedParameter = field(default=None)
    similarity: float = 0.0
    force_crossfade: bool = False
    
    def __post_init__(self):
        if self.progress is None:
            self.progress = AnimatedParameter(
                frames=15,
                method=InterpolationMethod.COSINE
            )
            self.progress.set_target(1.0)
        
        # вычисляем схожесть для автоматического выбора типа перехода
        if self.from_frame is not None:
            self.similarity = calculate_image_similarity(
                self.from_frame.pixels,
                self.to_frame.pixels
            )
            self.force_crossfade = is_bright_to_dark(self.from_frame.pixels, self.to_frame.pixels)
    
    @property
    def is_complete(self) -> bool:
        return self.progress.value >= 0.99


class TransitionEngine:
    """
    Движок переходов между кадрами.
    Применяется к финальным кадрам перед отправкой на дисплей.
    """
    
    def __init__(self):
        self.active_transition: FrameTransition | None = None
        self.default_duration: int = 15  # кадры
        self.default_method: InterpolationMethod = InterpolationMethod.COSINE
        self.auto_detect_type: bool = True  # автоматически выбирать тип перехода
    
    def start_transition(
        self,
        from_frame: Frame | None,
        to_frame: Frame,
        transition_type: TransitionType = TransitionType.MORPH,
        duration_frames: int | None = None,
        method: InterpolationMethod | None = None
    ):
        """Запускает переход между кадрами"""
        frames = duration_frames or self.default_duration
        interp_method = method or self.default_method
        
        progress = AnimatedParameter(
            frames=frames,
            method=interp_method
        )
        progress.set_target(1.0)
        
        self.active_transition = FrameTransition(
            from_frame=from_frame,
            to_frame=to_frame,
            transition_type=transition_type,
            progress=progress
        )
        
        # автоматический выбор типа перехода если включен
        if self.auto_detect_type and from_frame is not None:
            if self.active_transition.similarity >= SIMILARITY_THRESHOLD:
                self.active_transition.transition_type = TransitionType.MORPH
            else:
                self.active_transition.transition_type = TransitionType.JUMP
    
    def process(self, current_frame: Frame, dt: float) -> Frame:
        """
        Обрабатывает текущий кадр, применяя переход если он активен.
        """
        if self.active_transition is None:
            return current_frame
        
        # обновляем прогресс
        self.active_transition.progress.update(dt)
        
        if self.active_transition.is_complete:
            # переход завершен
            result = current_frame
            self.active_transition = None
            return result
        
        # применяем переход
        return self._apply_transition(self.active_transition, current_frame)
    
    def _apply_transition(self, transition: FrameTransition, current: Frame) -> Frame:
        """Применяет переход к кадрам"""
        t = transition.progress.value
        
        if transition.from_frame is None:
            # нет исходного кадра, просто появление
            return self._apply_fade_in(current, t)
        
        # Если принудительный кроссфейд (например, с белого на черный)
        if transition.force_crossfade:
            return self._crossfade(transition.from_frame, current, t)
            
        tt = transition.transition_type
        
        if tt == TransitionType.CROSSFADE:
            return self._crossfade(transition.from_frame, current, t)
        elif tt == TransitionType.MORPH:
            return self._morph(transition.from_frame, current, t)
        elif tt == TransitionType.JUMP:
            return self._jump(transition.from_frame, current, t)
        else:
            return current
    
    def _apply_fade_in(self, frame: Frame, t: float) -> Frame:
        """Плавное появление кадра"""
        result = Frame(frame.width, frame.height)
        result.pixels = (frame.pixels * t).astype(np.uint8)
        return result
    
    def _crossfade(self, from_frame: Frame, to_frame: Frame, t: float) -> Frame:
        """Кроссфейд между кадрами"""
        result = Frame(to_frame.width, to_frame.height)
        
        smooth_t = cosine_interpolation(0.0, 1.0, t)
        
        result.pixels = lerp_array(
            from_frame.pixels.astype(np.float32),
            to_frame.pixels.astype(np.float32),
            smooth_t
        ).astype(np.uint8)
        
        return result
    
    def _morph(self, from_frame: Frame, to_frame: Frame, t: float) -> Frame:
        """Попиксельный морфинг"""
        result = Frame(to_frame.width, to_frame.height)
        
        # используем плавную интерполяцию
        smooth_t = cosine_interpolation(0.0, 1.0, t)
        
        result.pixels = lerp_array(
            from_frame.pixels.astype(np.float32),
            to_frame.pixels.astype(np.float32),
            smooth_t
        ).astype(np.uint8)
        
        return result
    
    def _jump(self, from_frame: Frame, to_frame: Frame, t: float) -> Frame:
        """
        Прыжок новой картинки поверх старой снизу вверх.
        Черный цвет считается прозрачным.
        Старая картинка плавно исчезает в конце.
        """
        result = Frame(to_frame.width, to_frame.height)
        height, width = to_frame.height, to_frame.width
        
        # Плавное исчезновение старого кадра
        fade_out = 1.0 - (t ** 2)
        result.pixels[:] = (from_frame.pixels.astype(np.float32) * fade_out).astype(np.uint8)
        
        # вычисляем текущую позицию Y для новой картинки (от height до 0)
        current_y = int((1.0 - t) * height)
        
        # накладываем новый кадр со смещением
        if current_y < height:
            visible_h = height - current_y
            new_part = to_frame.pixels[0:visible_h, :]
            
            # Маска для не-черных пикселей
            mask = np.any(new_part > 0, axis=2)
            
            # Накладываем только там, где маска True
            target_area = result.pixels[current_y:height, :]
            target_area[mask] = new_part[mask]
            
        return result
    
    @property
    def is_transitioning(self) -> bool:
        """Есть ли активный переход"""
        return self.active_transition is not None
    
    def cancel(self):
        """Отменяет текущий переход"""
        self.active_transition = None
