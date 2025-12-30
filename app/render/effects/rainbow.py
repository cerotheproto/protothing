import numpy as np
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
    
    # конвертируем HSV в RGB
    rgb = _hsv_to_rgb(hue, np.ones_like(hue), np.ones_like(hue))
    
    # применяем оригинальную яркость для каждого канала
    result = np.zeros_like(pixels)
    for i in range(3):
        result[:, :, i] = rgb[:, :, i] * (brightness / 255.0)
    
    # Смешиваем оригинальный цвет и эффект в зависимости от прогресса
    final_pixels = pixels * (1.0 - effect._fade_progress) + result * effect._fade_progress

    # применяем только к не-чёрным пикселям
    frame.pixels[non_black_mask] = final_pixels[non_black_mask].astype(np.uint8)


def _hsv_to_rgb(h: np.ndarray, s: np.ndarray, v: np.ndarray) -> np.ndarray:
    """
    Конвертирует HSV в RGB.
    h, s, v: массивы значений от 0 до 1
    Возвращает RGB массив с значениями от 0 до 255
    """
    h = h * 6.0  # масштабируем hue до 0-6
    i = np.floor(h).astype(np.int32)
    f = h - i
    
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))
    
    i = i % 6
    
    # выбираем правильные компоненты в зависимости от i
    rgb = np.zeros((*h.shape, 3), dtype=np.float32)
    
    mask0 = (i == 0)
    mask1 = (i == 1)
    mask2 = (i == 2)
    mask3 = (i == 3)
    mask4 = (i == 4)
    mask5 = (i == 5)
    
    rgb[mask0, 0] = v[mask0]
    rgb[mask0, 1] = t[mask0]
    rgb[mask0, 2] = p[mask0]
    
    rgb[mask1, 0] = q[mask1]
    rgb[mask1, 1] = v[mask1]
    rgb[mask1, 2] = p[mask1]
    
    rgb[mask2, 0] = p[mask2]
    rgb[mask2, 1] = v[mask2]
    rgb[mask2, 2] = t[mask2]
    
    rgb[mask3, 0] = p[mask3]
    rgb[mask3, 1] = q[mask3]
    rgb[mask3, 2] = v[mask3]
    
    rgb[mask4, 0] = t[mask4]
    rgb[mask4, 1] = p[mask4]
    rgb[mask4, 2] = v[mask4]
    
    rgb[mask5, 0] = v[mask5]
    rgb[mask5, 1] = p[mask5]
    rgb[mask5, 2] = q[mask5]
    
    return rgb * 255.0
