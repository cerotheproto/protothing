import numpy as np
from render.frame import Frame
from render.frame_description import DizzyEffect
# это должно было быть субпиксельная версия wiggle, но в итоге оно просто плывёт волнами, поэтому назвал dizzy

def dizzy_effect(frame: Frame, effect: DizzyEffect, dt: float) -> None:
    """
    Применяет субпиксельное смещение к готовому кадру.
    Каждый пиксель смещается по синусоиде в зависимости от координат,
    создавая эффект "дыхания" или "текучести".
    
    """
    if effect.amplitude <= 0.001:
        return

    effect._phase += dt * effect.speed * 2.0 * np.pi

    height, width = frame.pixels.shape[:2]
    if width == 0 or height == 0:
        return

    # создаём сетку координат
    y_coords, x_coords = np.meshgrid(
        np.arange(height, dtype=np.float32),
        np.arange(width, dtype=np.float32),
        indexing='ij'
    )

    # нормализуем координаты для волны
    x_norm = x_coords / max(width, 1) * effect.wave_scale
    y_norm = y_coords / max(height, 1) * effect.wave_scale

    # вычисляем смещения на основе синусоиды (как в ProtoTracer)
    phase = effect._phase
    
    # смещение по X зависит от Y координаты (горизонтальная волна)
    offset_x = np.sin(y_norm * np.pi * 2.0 + phase) * effect.amplitude
    # смещение по Y зависит от X координаты (вертикальная волна)
    offset_y = np.sin(x_norm * np.pi * 2.0 + phase * 1.3) * effect.amplitude * effect.vertical_ratio

    # вычисляем исходные координаты для сэмплирования (обратное отображение)
    src_x = x_coords - offset_x
    src_y = y_coords - offset_y

    # применяем билинейную интерполяцию
    result = _bilinear_sample(frame.pixels, src_x, src_y)
    frame.pixels[:] = result


def _bilinear_sample(pixels: np.ndarray, src_x: np.ndarray, src_y: np.ndarray) -> np.ndarray:
    """Билинейная интерполяция для субпиксельного сэмплирования"""
    height, width = pixels.shape[:2]
    
    # ограничиваем координаты границами изображения
    src_x = np.clip(src_x, 0, width - 1.001)
    src_y = np.clip(src_y, 0, height - 1.001)

    # целые части координат
    x0 = src_x.astype(np.int32)
    y0 = src_y.astype(np.int32)
    x1 = np.minimum(x0 + 1, width - 1)
    y1 = np.minimum(y0 + 1, height - 1)

    # дробные части для интерполяции
    fx = (src_x - x0).astype(np.float32)
    fy = (src_y - y0).astype(np.float32)

    # расширяем для broadcasting по каналам
    fx = fx[:, :, np.newaxis]
    fy = fy[:, :, np.newaxis]

    # получаем четыре соседних пикселя
    p00 = pixels[y0, x0].astype(np.float32)
    p01 = pixels[y0, x1].astype(np.float32)
    p10 = pixels[y1, x0].astype(np.float32)
    p11 = pixels[y1, x1].astype(np.float32)

    # билинейная интерполяция
    result = (
        p00 * (1 - fx) * (1 - fy) +
        p01 * fx * (1 - fy) +
        p10 * (1 - fx) * fy +
        p11 * fx * fy
    )

    return np.clip(result, 0, 255).astype(np.uint8)
