import numpy as np
from render.frame import Frame
from render.frame_description import RainbowEffect
from typing import Optional


def _hsv_to_rgb_single(h: float, s: float = 1.0, v: float = 1.0) -> tuple[int, int, int]:
    """Конвертирует HSV в RGB для одного пикселя"""
    h = h * 6.0
    i = int(h) % 6
    f = h - int(h)
    
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))
    
    if i == 0:
        r, g, b = v, t, p
    elif i == 1:
        r, g, b = q, v, p
    elif i == 2:
        r, g, b = p, v, t
    elif i == 3:
        r, g, b = p, q, v
    elif i == 4:
        r, g, b = t, p, v
    else:
        r, g, b = v, p, q
    
    return (int(r * 255), int(g * 255), int(b * 255))


def get_most_common_color(frame: Frame) -> tuple[int, int, int]:
    """Находит самый встречаемый цвет на кадре (исключая черный)"""
    pixels = frame.pixels.reshape(-1, 3)
    
    # фильтруем черные пиксели
    non_black_mask = np.any(pixels > 0, axis=1)
    non_black_pixels = pixels[non_black_mask]
    
    if len(non_black_pixels) == 0:
        return (0, 0, 0)
    
    # квантуем цвета для ускорения (делим на 16)
    quantized = (non_black_pixels // 16) * 16
    
    # находим уникальные цвета и их количество
    unique, counts = np.unique(quantized, axis=0, return_counts=True)
    
    # возвращаем самый частый
    most_common_idx = np.argmax(counts)
    return tuple(unique[most_common_idx])


def generate_led_strip_pixels(
    led_count: int,
    frame: Frame,
    rainbow_effect: Optional[RainbowEffect]
) -> bytes:
    """
    Формирует RGB данные для LED ленты.
    Если есть RainbowEffect - генерирует радугу синхронизированную с эффектом.
    Иначе - заполняет самым встречаемым цветом кадра.
    """
    pixels = bytearray(led_count * 3)
    
    if rainbow_effect is not None and rainbow_effect.speed > 0.001:
        # радуга синхронизированная с эффектом на экране
        for i in range(led_count):
            # распределяем hue по длине ленты + текущая фаза эффекта
            hue = (i / led_count + rainbow_effect._phase / (2.0 * np.pi)) % 1.0
            r, g, b = _hsv_to_rgb_single(hue)
            pixels[i * 3] = r
            pixels[i * 3 + 1] = g
            pixels[i * 3 + 2] = b
    else:
        # заполняем самым частым цветом
        color = get_most_common_color(frame)
        for i in range(led_count):
            pixels[i * 3] = color[0]
            pixels[i * 3 + 1] = color[1]
            pixels[i * 3 + 2] = color[2]
    
    return bytes(pixels)


def find_rainbow_effect(effects: list) -> Optional[RainbowEffect]:
    """Ищет RainbowEffect в списке эффектов"""
    for effect in effects:
        if isinstance(effect, RainbowEffect):
            return effect
    return None
