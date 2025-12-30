import numpy as np
from render.frame import Frame
from render.frame_description import ColorOverrideEffect


def color_override_effect(frame: Frame, effect: ColorOverrideEffect, dt: float) -> None:
    """
    Переопределяет цвет всех не-черных/не-прозрачных пикселей на заданный цвет.
    Добавляет статичные диагональные полосы, где цвет плавно переходит между base_color и glare_color.
    """
    height, width = frame.pixels.shape[:2]
    if width == 0 or height == 0:
        return

    pixels = frame.pixels.astype(np.float32)
    
    # находим не-черные пиксели (где хотя бы один канал > 0)
    brightness = np.max(pixels, axis=2)
    non_black_mask = brightness > 0
    
    if not np.any(non_black_mask):
        return
    
    # применяем основной цвет
    base_color = np.array(effect.base_color[:3], dtype=np.float32)
    
    # сохраняем яркость оригинального пикселя
    for i in range(3):
        pixels[:, :, i] = base_color[i] * (brightness / 255.0)
    
    # добавляем эффект блика, если включен
    if effect.glare_enabled:
        # инициализация генератора случайных чисел и позиций бликов
        if effect._rng_state is None:
            seed = effect.seed if effect.seed is not None else int(np.random.randint(0, 2**31))
            effect._rng_state = np.random.Generator(np.random.PCG64(seed))
        
        if effect._glare_positions is None:
            effect._glare_positions = []
            for _ in range(effect.glare_count):
                # случайная позиция на диагонали и ширина полосы (градиента)
                diagonal_pos = effect._rng_state.uniform(0.0, 1.0)
                band_width = effect._rng_state.uniform(0.05, 0.15)
                effect._glare_positions.append((diagonal_pos, band_width))
        
        # создаем координаты пикселей
        height_array, width_array = np.meshgrid(
            np.arange(height, dtype=np.float32) / max(height, 1),
            np.arange(width, dtype=np.float32) / max(width, 1),
            indexing='ij'
        )
        
        # диагональная координата каждого пикселя
        diagonal = (height_array + width_array) / 2.0
        
        glare_color = np.array(effect.glare_color[:3], dtype=np.float32)
        
        # обработка каждой диагональной полосы с градиентом
        for diag_pos, band_width in effect._glare_positions:
            # расстояние от центра полосы
            distance_to_band = np.abs(diagonal - diag_pos)
            
            # плавный градиент (переход от glare_color в центре к base_color по краям)
            # использует гауссову кривую для плавного перехода
            gradient_mask = np.exp(-distance_to_band**2 / (2.0 * band_width**2))
            
            # применяем градиент цвета
            for i in range(3):
                # блендим между base_color и glare_color в зависимости от расстояния
                blended_color = (
                    base_color[i] * (1.0 - gradient_mask) +
                    glare_color[i] * gradient_mask
                )
                # применяем с интенсивностью эффекта
                pixels[:, :, i] = (
                    pixels[:, :, i] * (1.0 - effect.glare_intensity) +
                    blended_color * effect.glare_intensity
                )
    
    # применяем только к не-черным пикселям
    frame.pixels[non_black_mask] = pixels[non_black_mask].astype(np.uint8)
