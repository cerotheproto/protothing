from render.frame import Frame
from render.frame_description import RectLayer

def rect_layer(frame: Frame, layer: RectLayer, dt: float) -> None:
    """Draws a rectangle on the frame with alpha blending"""
    x_start = int(layer.x)
    y_start = int(layer.y)
    x_end = int(layer.x + layer.width)
    y_end = int(layer.y + layer.height)
    
    # Clamp coordinates to frame bounds
    x_start = max(0, min(frame.width, x_start))
    y_start = max(0, min(frame.height, y_start))
    x_end = max(0, min(frame.width, x_end))
    y_end = max(0, min(frame.height, y_end))
    
    if x_start >= x_end or y_start >= y_end:
        return
    
    r, g, b, a = layer.color
    alpha = a / 255.0
    
    # Draw rectangle with alpha blending
    for y in range(y_start, y_end):
        for x in range(x_start, x_end):
            dst_r, dst_g, dst_b = frame.pixels[y, x]
            frame.pixels[y, x, 0] = int(r * alpha + dst_r * (1 - alpha))
            frame.pixels[y, x, 1] = int(g * alpha + dst_g * (1 - alpha))
            frame.pixels[y, x, 2] = int(b * alpha + dst_b * (1 - alpha))