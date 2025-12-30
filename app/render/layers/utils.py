import numpy as np
from render.frame import Frame

def render_subpixel_sprite(frame: Frame, sprite_data: np.ndarray, x: float, y: float) -> None:
    """
    Renders a sprite with sub-pixel positioning using bilinear interpolation.
    sprite_data: RGBA numpy array of shape (H, W, 4), dtype=uint8
    x, y: float coordinates
    """
    h, w, _ = sprite_data.shape
    
    # 1. Разделяем координаты
    x_int = int(np.floor(x))
    y_int = int(np.floor(y))
    fx = x - x_int
    fy = y - y_int
    
    # 2. Подготовка спрайта (premultiplied alpha)
    sprite_float = sprite_data.astype(np.float32)
    # Нормализуем альфу для умножения
    alpha_norm = sprite_float[..., 3:4] / 255.0
    # Premultiply RGB
    sprite_float[..., :3] *= alpha_norm
    
    # 3. Создаем расширенный спрайт (интерполяция)
    # Мы распределяем энергию пикселя на 4 соседних
    expanded = np.zeros((h + 1, w + 1, 4), dtype=np.float32)
    
    w00 = (1 - fx) * (1 - fy)
    w10 = fx * (1 - fy)
    w01 = (1 - fx) * fy
    w11 = fx * fy
    
    # Векторизованное сложение
    expanded[0:h, 0:w] += sprite_float * w00
    expanded[0:h, 1:w+1] += sprite_float * w10
    expanded[1:h+1, 0:w] += sprite_float * w01
    expanded[1:h+1, 1:w+1] += sprite_float * w11
    
    # 4. Вычисляем границы отрисовки (clipping)
    exp_x_start = max(0, x_int)
    exp_y_start = max(0, y_int)
    exp_x_end = min(frame.width, x_int + w + 1)
    exp_y_end = min(frame.height, y_int + h + 1)
    
    if exp_x_start >= exp_x_end or exp_y_start >= exp_y_end:
        return

    # Смещения внутри expanded
    offset_x = exp_x_start - x_int
    offset_y = exp_y_start - y_int
    
    width_draw = exp_x_end - exp_x_start
    height_draw = exp_y_end - exp_y_start
    
    visible_sprite = expanded[offset_y:offset_y+height_draw, offset_x:offset_x+width_draw]
    
    # 5. Блендинг
    visible_frame = frame.pixels[exp_y_start:exp_y_end, exp_x_start:exp_x_end].astype(np.float32)
    
    sprite_rgb_premul = visible_sprite[..., :3]
    sprite_alpha = visible_sprite[..., 3:4] / 255.0
    
    # Пороговое значение для альфы, чтобы избежать полупрозрачности на краях
    # Но сохраняем интерполяцию цветов внутри
    mask = sprite_alpha[..., 0] > 0.5
    
    if not np.any(mask):
        return
        
    # Для пикселей, прошедших порог, делаем альфу 1.0 (полная непрозрачность)
    # Но цвета оставляем интерполированными (но нужно де-премультиплицировать?)
    # У нас sprite_rgb_premul уже умножен на альфу (которая была дробной).
    # Если мы хотим "жесткий" край, но "мягкий" цвет внутри...
    # Если мы просто наложим blended, то на краях будет полупрозрачность.
    # Если мы используем mask, то мы пишем ТОЛЬКО там где mask=True.
    # И пишем мы blended?
    # Если alpha=0.6, blended = color*0.6 + bg*0.4. Это полупрозрачность.
    # Нам нужно: если alpha > 0.5, то color = color_interpolated (без смешивания с фоном).
    # Но color_interpolated у нас в sprite_rgb_premul (умножен на alpha).
    # Нам нужно восстановить цвет: color = sprite_rgb_premul / alpha.
    
    # Восстанавливаем RGB (де-премультипликация)
    # Избегаем деления на 0
    safe_alpha = np.maximum(sprite_alpha, 1e-6)
    sprite_rgb_restored = sprite_rgb_premul / safe_alpha
    
    # Теперь записываем sprite_rgb_restored прямо в кадр там, где mask=True
    # Это даст жесткие края (mask) и интерполированные цвета (bilinear sampling).
    
    target_area = frame.pixels[exp_y_start:exp_y_end, exp_x_start:exp_x_end]
    
    # Используем маску для записи
    # Нам нужно привести к uint8
    pixels_to_write = np.clip(sprite_rgb_restored, 0, 255).astype(np.uint8)
    
    target_area[mask] = pixels_to_write[mask]

