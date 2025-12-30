import numpy as np
from render.frame import Frame
from render.frame_description import SpriteLayer
from render.layers.utils import render_subpixel_sprite


def sprite_layer(frame: Frame, layer: SpriteLayer) -> None:
    """Отрисовывает спрайт на кадре с учетом альфа-канала и субпиксельного сглаживания"""
    # преобразуем спрайт в numpy массив (RGBA)
    sprite_data = np.frombuffer(layer.image, dtype=np.uint8).reshape(
        layer.sprite_height, layer.sprite_width, 4
    )
    
    render_subpixel_sprite(frame, sprite_data, layer.x, layer.y)

