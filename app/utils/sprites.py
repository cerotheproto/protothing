from render.frame_description import SpriteLayer, AnimatedSpriteLayer
from PIL import Image
from typing import Union

# глобальный кеш загруженных спрайтов
_sprite_cache: dict[str, Union[SpriteLayer, AnimatedSpriteLayer]] = {}


def load_sprite(image_path: str, x: int = 0, y: int = 0, use_cache: bool = True) -> SpriteLayer:
    """Загружает PNG изображение и возвращает SpriteLayer с кешированием"""
    cache_key = f"static:{image_path}:{x}:{y}"
    
    if use_cache and cache_key in _sprite_cache:
        cached = _sprite_cache[cache_key]
        if isinstance(cached, SpriteLayer):
            # возвращаем копию с текущими координатами
            return SpriteLayer(
                image=cached.image,
                sprite_width=cached.sprite_width,
                sprite_height=cached.sprite_height,
                x=x,
                y=y
            )
    
    image = Image.open(image_path)
    
    # конвертируем в RGBA если нужно
    if image.mode != 'RGBA':
        image = image.convert('RGBA')
    
    # получаем размеры
    width, height = image.size
    
    # преобразуем в байты (RGBA)
    image_data = bytes(image.tobytes())
    
    sprite = SpriteLayer(
        image=image_data,
        sprite_width=width,
        sprite_height=height,
        x=x,
        y=y
    )
    
    if use_cache:
        _sprite_cache[cache_key] = sprite
    
    return sprite


def load_animated_sprite(gif_path: str, x: int = 0, y: int = 0, use_cache: bool = True) -> AnimatedSpriteLayer:
    """Загружает GIF анимацию и возвращает AnimatedSpriteLayer с кешированием"""
    cache_key = f"animated:{gif_path}:{x}:{y}"
    
    if use_cache and cache_key in _sprite_cache:
        cached = _sprite_cache[cache_key]
        if isinstance(cached, AnimatedSpriteLayer):
            # возвращаем копию с текущими координатами
            return AnimatedSpriteLayer(
                frames=cached.frames,
                frame_durations=cached.frame_durations,
                sprite_width=cached.sprite_width,
                sprite_height=cached.sprite_height,
                x=x,
                y=y,
                current_frame=0,
                elapsed_time=0.0,
                loop=True
            )
    
    image = Image.open(gif_path)
    
    frames = []
    durations = []
    
    # извлекаем все фреймы из GIF
    try:
        frame_index = 0
        while True:
            image.seek(frame_index)
            
            # конвертируем в RGBA
            frame = image.convert('RGBA')
            frames.append(bytes(frame.tobytes()))
            
            # длительность фрейма в миллисекундах, конвертируем в секунды
            duration = image.info.get('duration', 100) / 1000.0
            durations.append(duration)
            
            frame_index += 1
    except EOFError:
        pass  # достигли конца GIF
    
    if not frames:
        raise ValueError(f"GIF файл {gif_path} не содержит фреймов")
    
    width, height = image.size
    
    sprite = AnimatedSpriteLayer(
        frames=frames,
        frame_durations=durations,
        sprite_width=width,
        sprite_height=height,
        x=x,
        y=y,
        current_frame=0,
        elapsed_time=0.0,
        loop=True
    )
    
    if use_cache:
        _sprite_cache[cache_key] = sprite
    
    return sprite


def clear_sprite_cache():
    """Очищает кеш спрайтов"""
    _sprite_cache.clear()
