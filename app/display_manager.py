import numpy as np
from render.frame import Frame
from enum import Enum


class MirrorMode(Enum):
    NONE = "none"
    LEFT = "left"
    RIGHT = "right"


class DisplayManager:
    """
    Менеджер отображения. Расширяет кадры 64x32 до 128x32.
    Поддерживает отражение левой или правой половины.
    """
    
    def __init__(self):
        self.mirror_mode = MirrorMode.NONE
    
    def set_mirror_mode(self, mode: MirrorMode) -> None:
        """Устанавливает режим отражения"""
        self.mirror_mode = mode
    
    def process_frame(self, frame: Frame) -> Frame:
        """
        Обрабатывает кадр: расширяет 64x32 до 128x32 и применяет отражение.
        Также применяет режим зеркалирования к уже готовым 128x32 кадрам.
        """
        # Expand and mirror 64x32 frames as before
        if frame.width == 64 and frame.height == 32:
            return self._expand_and_mirror(frame)
        
        # If frame is already 128x32, apply mirror mode to halves
        if frame.width == 128 and frame.height == 32:
            if self.mirror_mode == MirrorMode.NONE:
                return frame

            left = frame.pixels[:, :64]
            right = frame.pixels[:, 64:]
            result = Frame(width=128, height=32)

            if self.mirror_mode == MirrorMode.LEFT:
                left_mirrored = np.fliplr(left)
                result.pixels[:, :64] = left_mirrored
                result.pixels[:, 64:] = right
            elif self.mirror_mode == MirrorMode.RIGHT:
                right_mirrored = np.fliplr(right)
                result.pixels[:, :64] = left
                result.pixels[:, 64:] = right_mirrored

            return result

        return frame
    
    def _expand_and_mirror(self, frame: Frame) -> Frame:
        """Расширяет кадр 64x32 до 128x32 с отражением"""
        expanded = Frame(width=128, height=32)
        
        if self.mirror_mode == MirrorMode.NONE:
            # просто копируем левую половину в обе части
            expanded.pixels[:, :64] = frame.pixels
            expanded.pixels[:, 64:] = frame.pixels
        
        elif self.mirror_mode == MirrorMode.LEFT:
            # отражаем левую половину (зеркальное отражение слева)
            left_mirrored = np.fliplr(frame.pixels)
            expanded.pixels[:, :64] = left_mirrored
            expanded.pixels[:, 64:] = frame.pixels
        
        elif self.mirror_mode == MirrorMode.RIGHT:
            # отражаем правую половину (зеркальное отражение справа)
            right_mirrored = np.fliplr(frame.pixels)
            expanded.pixels[:, :64] = frame.pixels
            expanded.pixels[:, 64:] = right_mirrored
        
        return expanded
