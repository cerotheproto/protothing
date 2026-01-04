import numpy as np
import cv2
from render.frame import Frame
from render.frame_description import RainbowEffect


def rainbow_effect(frame: Frame, effect: RainbowEffect, dt: float) -> None:
    """
    Применяет эффект переливания радуги ко всем не-чёрным пикселям.
    Каждый пиксель переливается по спектру в зависимости от времени.
    """
    if effect.speed <= 0.001:
        return

    # --- State Management ---
    if effect._is_stopping and effect._state != 'fade_out' and effect._state != 'finished':
        effect._state = 'fade_out'

    if effect._state == 'fade_in':
        effect._fade_progress += dt / max(effect.fade_in_duration, 0.001)
        if effect._fade_progress >= 1.0:
            effect._fade_progress = 1.0
            effect._state = 'running'
    elif effect._state == 'running':
        effect._fade_progress = 1.0
    elif effect._state == 'fade_out':
        effect._fade_progress -= dt / max(effect.fade_out_duration, 0.001)
        if effect._fade_progress <= 0.0:
            effect._fade_progress = 0.0
            effect._state = 'finished'
            return # Effect finished
    elif effect._state == 'finished':
        return

    # обновляем фазу
    effect._phase += dt * effect.speed * 2.0 * np.pi
    if effect._phase > 2.0 * np.pi:
        effect._phase -= 2.0 * np.pi

    height, width = frame.pixels.shape[:2]
    if width == 0 or height == 0:
        return

    # получаем все пиксели
    pixels = frame.pixels.astype(np.float32)
    
    # находим не-чёрные пиксели (где хотя бы один канал > 0)
    brightness = np.max(pixels, axis=2)
    non_black_mask = brightness > 0
    
    if not np.any(non_black_mask):
        return
    
    # вычисляем HSV цвета для всех пикселей на основе фазы
    height_array, width_array = np.meshgrid(
        np.arange(height, dtype=np.float32),
        np.arange(width, dtype=np.float32),
        indexing='ij'
    )
    
    # оттенок (hue) зависит от позиции + фаза для переливания
    if effect.use_position:
        # вариант с циклом по экрану
        hue = (height_array / max(height, 1) - width_array / max(width, 1)) * 0.5
        hue = (hue + effect._phase / (2.0 * np.pi)) % 1.0
    else:
        # просто фаза для всех пикселей одинаково
        hue = np.full((height, width), (effect._phase / (2.0 * np.pi)) % 1.0)
    
    # convert HSV to RGB using cv2 (optimized)
    hsv = np.stack([hue * 180, np.ones_like(hue) * 255, np.ones_like(hue) * 255], axis=-1).astype(np.uint8)
    rgb = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB).astype(np.float32)
    
    # apply original brightness to each channel
    result = rgb * (brightness[:, :, np.newaxis] / 255.0)
    
    # Смешиваем оригинальный цвет и эффект в зависимости от прогресса
    final_pixels = pixels * (1.0 - effect._fade_progress) + result * effect._fade_progress

    # применяем только к не-чёрным пикселям
    frame.pixels[non_black_mask] = final_pixels[non_black_mask].astype(np.uint8)



