import numpy as np
from numpy.random import default_rng
from render.frame import Frame
from render.frame_description import ShakeEffect


def shake_effect(frame: Frame, effect: ShakeEffect, dt: float) -> None:
    """
    Применяет эффект тряски к кадру.
    Добавляет случайные смещения пикселей, создавая иллюзию дрожания.
    """
    if effect.amplitude <= 0.001:
        return

    # инициализируем генератор случайных чисел
    if effect._rng_state is None:
        effect._rng_state = default_rng(effect.seed)

    rng = effect._rng_state

    # обновляем смещение с заданной частотой
    change_interval = 1.0 / max(effect.frequency, 0.1)
    effect._shake_time = getattr(effect, '_shake_time', 0.0)
    effect._shake_time += dt

    if effect._shake_time >= change_interval:
        effect._shake_time -= change_interval
        # генерируем случайный вектор смещения
        effect._shake_offset = rng.normal(0, effect.amplitude / 3.0, size=2).astype(np.float32)
        effect._shake_offset = np.clip(effect._shake_offset, -effect.amplitude, effect.amplitude)

    height, width = frame.pixels.shape[:2]
    if width == 0 or height == 0:
        return

    # смещение по пикселям
    offset_x = int(np.round(effect._shake_offset[0]))
    offset_y = int(np.round(effect._shake_offset[1]))

    if offset_x == 0 and offset_y == 0:
        return

    # применяем смещение
    frame.pixels[:] = _apply_offset(frame.pixels, offset_x, offset_y)


def _apply_offset(pixels: np.ndarray, offset_x: int, offset_y: int) -> np.ndarray:
    """
    Смещает пиксели на заданное количество позиций.
    Пиксели за границами заполняются черным цветом.
    """
    result = np.zeros_like(pixels)
    height, width = pixels.shape[:2]

    # вычисляем область копирования
    src_y_start = max(0, -offset_y)
    src_y_end = min(height, height - offset_y)
    dst_y_start = max(0, offset_y)
    dst_y_end = min(height, height + offset_y)

    src_x_start = max(0, -offset_x)
    src_x_end = min(width, width - offset_x)
    dst_x_start = max(0, offset_x)
    dst_x_end = min(width, width + offset_x)

    # копируем пиксели с смещением
    src_height = src_y_end - src_y_start
    src_width = src_x_end - src_x_start
    dst_height = dst_y_end - dst_y_start
    dst_width = dst_x_end - dst_x_start

    if src_height > 0 and src_width > 0:
        height_to_copy = min(src_height, dst_height)
        width_to_copy = min(src_width, dst_width)
        result[dst_y_start:dst_y_start + height_to_copy, dst_x_start:dst_x_start + width_to_copy] = \
            pixels[src_y_start:src_y_start + height_to_copy, src_x_start:src_x_start + width_to_copy]

    return result
