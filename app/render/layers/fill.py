
from render.frame import Frame
from render.frame_description import FillLayer

def fill_layer(frame: Frame, layer: FillLayer) -> None:
    r, g, b, *_ = layer.color
    # заполняем весь кадр цветом напрямую
    frame.pixels[:, :] = [r, g, b]