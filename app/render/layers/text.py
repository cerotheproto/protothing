import numpy as np
from PIL import Image, ImageDraw, ImageFont
from render.frame import Frame
from render.frame_description import TextLayer
from render.layers.utils import render_subpixel_sprite
import os


def _get_default_unicode_font(size: int):
    """Находит системный шрифт с поддержкой Unicode"""
    font_paths = [
        "assets/font.otf", 
    ]
    
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    
    # если ничего не нашли, используем дефолтный (но он не поддерживает кириллицу)
    return ImageFont.load_default()


def text_layer(frame: Frame, layer: TextLayer) -> None:
    """Отрисовывает текст на кадре"""
    try:
        # загружаем шрифт
        if layer.font_path:
            font = ImageFont.truetype(layer.font_path, layer.font_size)
        else:
            # пытаемся найти системный шрифт с поддержкой Unicode
            font = _get_default_unicode_font(layer.font_size)
    except Exception:
        # если не удалось загрузить, пытаемся найти системный
        font = _get_default_unicode_font(layer.font_size)
    
    # создаем временное изображение для рендеринга текста
    # используем dummy для получения размеров текста
    dummy_img = Image.new('RGBA', (1, 1))
    dummy_draw = ImageDraw.Draw(dummy_img)
    
    # получаем размеры текста
    bbox = dummy_draw.textbbox((0, 0), layer.text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    if text_width <= 0 or text_height <= 0:
        return
    
    # создаем изображение нужного размера с прозрачным фоном
    text_img = Image.new('RGBA', (text_width, text_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_img)
    
    # рисуем текст
    draw.text((-bbox[0], -bbox[1]), layer.text, fill=layer.color, font=font)
    
    # конвертируем в numpy массив
    text_data = np.array(text_img, dtype=np.uint8)
    
    # используем существующую функцию для отрисовки с субпиксельным позиционированием
    render_subpixel_sprite(frame, text_data, layer.x, layer.y)
