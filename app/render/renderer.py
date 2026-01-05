from render.frame import Frame
from render.frame_description import FrameDescription, FillLayer, SpriteLayer, AnimatedSpriteLayer, TextLayer, RectLayer, WiggleEffect, DizzyEffect, RainbowEffect, ShakeEffect
from render.layers.fill import fill_layer
from render.layers.sprite import sprite_layer
from render.layers.animated_sprite import animated_sprite_layer
from render.layers.text import text_layer
from render.layers.rect import rect_layer
from render.effects.wiggle import wiggle_effect
from render.effects.dizzy import dizzy_effect
from render.effects.rainbow import rainbow_effect
from render.effects.shake import shake_effect

class Renderer:
    
    def render_frame(self, frame_desc: FrameDescription, dt: float = 0.0) -> Frame:
        frame = Frame(frame_desc.width, frame_desc.height)

        if frame_desc.effects:
            self._apply_effects(frame_desc.layers, frame_desc.effects, dt)

        for layer in frame_desc.layers:
            if isinstance(layer, FillLayer):
                fill_layer(frame, layer)
            elif isinstance(layer, AnimatedSpriteLayer):
                animated_sprite_layer(frame, layer, dt)
            elif isinstance(layer, SpriteLayer):
                sprite_layer(frame, layer)
            elif isinstance(layer, TextLayer):
                text_layer(frame, layer)
            elif isinstance(layer, RectLayer):
                rect_layer(frame, layer, dt)

        # применяем пост-эффекты к готовому кадру
        if frame_desc.effects:
            self._apply_post_effects(frame, frame_desc.effects, dt)

        return frame

    def _apply_effects(self, layers: list, effects: list, dt: float) -> None:
        for effect in effects:
            if isinstance(effect, WiggleEffect):
                wiggle_effect(layers, effect, dt)

    def _apply_post_effects(self, frame: Frame, effects: list, dt: float) -> None:
        for effect in effects:
            if isinstance(effect, DizzyEffect):
                dizzy_effect(frame, effect, dt)
            elif isinstance(effect, RainbowEffect):
                rainbow_effect(frame, effect, dt)
            elif isinstance(effect, ShakeEffect):
                shake_effect(frame, effect, dt)