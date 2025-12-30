import numpy as np
from render.frame import Frame
from render.frame_description import AnimatedSpriteLayer
from render.layers.utils import render_subpixel_sprite


def animated_sprite_layer(frame: Frame, layer: AnimatedSpriteLayer, dt: float) -> None:
    """Отрисовывает анимированный спрайт на кадре с учетом альфа-канала и обновлением времени"""
    
    # обновляем время анимации
    layer.elapsed_time += dt
    
    # переключаем фреймы по времени
    current_duration = layer.frame_durations[layer.current_frame]
    
    if layer.elapsed_time >= current_duration:
        layer.elapsed_time -= current_duration
        layer._previous_frame = layer.current_frame
        layer.current_frame += 1
        
        # зацикливание
        if layer.current_frame >= len(layer.frames):
            if layer.loop:
                layer.current_frame = 0
                # для не-loop режима или пинг-понга: проверяем если это не первый цикл
                if not layer._completed_once and layer.on_complete:
                    layer._completed_once = True
                    layer.on_complete()
                    layer.on_complete = None
            else:
                layer.current_frame = len(layer.frames) - 1  # остаемся на последнем фрейме
                # вызываем callback при завершении
                if not layer._completed_once and layer.on_complete:
                    layer._completed_once = True
                    layer.on_complete()
                    layer.on_complete = None  # чтобы не вызывать повторно
    
    # получаем текущий фрейм
    current_frame_data = layer.frames[layer.current_frame]
    
    # преобразуем спрайт в numpy массив (RGBA)
    sprite_data = np.frombuffer(current_frame_data, dtype=np.uint8).reshape(
        layer.sprite_height, layer.sprite_width, 4
    )
    
    render_subpixel_sprite(frame, sprite_data, layer.x, layer.y)

