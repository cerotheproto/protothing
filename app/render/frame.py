import numpy as np

# бинарный кадр RGB888 - numpy массив пикселей (3 байта на пиксель: R, G, B)

class Frame:

    def __init__(self, width: int = 64, height: int = 32):
        self.width = width
        self.height = height
        # храним как numpy массив с формой (height, width, 3)
        self.pixels = np.zeros((height, width, 3), dtype=np.uint8)
        
    def set_pixel(self, x: int, y: int, color: tuple[int, int, int]):
        """Устанавливает цвет пикселя (R, G, B) в координатах (x, y)"""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[y, x] = color

    def to_bytes(self) -> bytes:
        """Возвращает байтовое представление кадра"""
        return self.pixels.tobytes()
    

    