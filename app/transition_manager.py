"""
Менеджер переходов для пиксельного морфинга между частями лица.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from utils.transition import (
    InterpolationMethod, AnimatedParameter, 
    calculate_image_similarity, lerp_array, cosine_interpolation,
    is_bright_to_dark
)
from render.frame_description import SpriteLayer, AnimatedSpriteLayer
import numpy as np
import logging
logger = logging.getLogger(__name__)
if TYPE_CHECKING:
    from apps.reactive_face.face_parts import PartState


# порог схожести для выбора типа перехода
SIMILARITY_THRESHOLD = 0.1


@dataclass
class PartTransition:
    """Переход для одной части лица"""
    part_type: str
    from_state: "PartState | None"
    to_state: "PartState"
    progress: AnimatedParameter = field(default=None)
    similarity: float = 0.0
    force_crossfade: bool = False
    use_jump_transition: bool = False  # использовать прыжок для полного перехода
    _from_pixels: np.ndarray | None = field(default=None, repr=False)
    _to_pixels: np.ndarray | None = field(default=None, repr=False)
    _blended_pixels: np.ndarray | None = field(default=None, repr=False)
    _from_x: float = field(default=0.0, repr=False)  # исходная координата X
    _from_y: float = field(default=0.0, repr=False)  # исходная координата Y
    _to_x: float = field(default=0.0, repr=False)    # целевая координата X
    _to_y: float = field(default=0.0, repr=False)    # целевая координата Y
    
    def __post_init__(self):
        if self.progress is None:
            self.progress = AnimatedParameter(
                frames=12,
                method=InterpolationMethod.COSINE
            )
            self.progress.set_target(1.0)
        
        # кешируем пиксели и координаты
        self._cache_pixels()
    
    def _cache_pixels(self):
        """Кеширует пиксели состояний и координаты для быстрого смешивания"""
        # кешируем координаты
        if self.from_state is not None:
            self._from_pixels = self._extract_pixels(self.from_state.layer)
            self._from_x = self._get_coordinate(self.from_state.layer, 'x')
            self._from_y = self._get_coordinate(self.from_state.layer, 'y')
        else:
            self._from_x = 0.0
            self._from_y = 0.0
        
        self._to_pixels = self._extract_pixels(self.to_state.layer)
        self._to_x = self._get_coordinate(self.to_state.layer, 'x')
        self._to_y = self._get_coordinate(self.to_state.layer, 'y')
        
        # вычисляем схожесть если есть оба состояния
        if self._from_pixels is not None and self._to_pixels is not None:
            if self._from_pixels.shape == self._to_pixels.shape:
                self.similarity = calculate_image_similarity(
                    self._from_pixels, self._to_pixels
                )
            else:
                self.similarity = 0.0
            
            # Проверяем на переход от светлого к темному
            self.force_crossfade = is_bright_to_dark(self._from_pixels, self._to_pixels)
    
    def _extract_pixels(self, layer) -> np.ndarray | None:
        """Извлекает пиксели из слоя"""
        if isinstance(layer, SpriteLayer):
            # RGBA данные
            return np.frombuffer(layer.image, dtype=np.uint8).reshape(
                layer.sprite_height, layer.sprite_width, 4
            ).copy()
        elif isinstance(layer, AnimatedSpriteLayer):
            # берем текущий кадр анимации
            if layer.frames:
                frame_data = layer.frames[layer.current_frame]
                return np.frombuffer(frame_data, dtype=np.uint8).reshape(
                    layer.sprite_height, layer.sprite_width, 4
                ).copy()
        return None
    
    def _get_coordinate(self, layer, coord: str) -> float:
        """Получает координату из слоя"""
        if hasattr(layer, coord):
            return getattr(layer, coord)
        return 0.0
    
    @property
    def is_complete(self) -> bool:
        """Переход завершен"""
        return self.progress.value >= 0.99
    
    @property
    def use_morph(self) -> bool:
        """Использовать попиксельный морфинг или кроссфейд"""
        return self.similarity >= SIMILARITY_THRESHOLD and not self.force_crossfade


class TransitionManager:
    """
    Менеджер переходов между состояниями частей лица.
    
    Типы переходов:
    1. Попиксельный морфинг - для схожих изображений, плавное перетекание
    2. Накатывание - для разных изображений, новое "накатывается" на старое
    """
    
    def __init__(self):
        self.active_transitions: dict[str, PartTransition] = {}
        self.transition_duration: int = 140  # универсальная длительность на случай, если ничего не задано
        self.crossfade_duration: int = 40  # быстрый кроссфейд для несхожих частей
        self.morph_duration: int = 140  # затяжной морф для схожих картинок (≈2.3 с при 60fps)
        self.jump_duration: int = 60
        self.method: InterpolationMethod = InterpolationMethod.COSINE
    
    def start_transition(
        self, 
        part_type: str, 
        from_state: "PartState | None",
        to_state: "PartState",
        duration_frames: int | None = None,
        method: InterpolationMethod | None = None
    ):
        """Запускает переход для части лица"""
        transition = PartTransition(
            part_type=part_type,
            from_state=from_state,
            to_state=to_state,
        )
        
        if duration_frames is not None:
            frames = duration_frames
        elif transition.use_jump_transition:
            frames = self.jump_duration
        elif transition.use_morph:
            frames = self.morph_duration
        else:
            frames = self.crossfade_duration
        
        interp_method = method or self.method
        progress = AnimatedParameter(frames=frames, method=interp_method)
        progress.set_target(1.0)
        transition.progress = progress
        
        logger.debug(f"Transition {part_type}: similarity={transition.similarity:.3f}, use_morph={transition.use_morph}")
        
        self.active_transitions[part_type] = transition
    
    def update(self, dt: float):
        """Обновляет все активные переходы"""
        completed = []
        
        for part_type, transition in self.active_transitions.items():
            transition.progress.update(dt)
            
            if transition.is_complete:
                completed.append(part_type)
        
        # удаляем завершенные переходы
        for part_type in completed:
            del self.active_transitions[part_type]
    
    def get_transition(self, part_type: str) -> PartTransition | None:
        """Получает активный переход для части"""
        return self.active_transitions.get(part_type)
    
    def has_transition(self, part_type: str) -> bool:
        """Проверяет есть ли активный переход"""
        return part_type in self.active_transitions
    
    def cancel_transition(self, part_type: str):
        """Отменяет переход"""
        if part_type in self.active_transitions:
            del self.active_transitions[part_type]
    
    def clear_all(self):
        """Очищает все переходы"""
        self.active_transitions.clear()
    
    def blend_layer(
        self, 
        transition: PartTransition,
        base_layer: "SpriteLayer | AnimatedSpriteLayer"
    ) -> "SpriteLayer | AnimatedSpriteLayer":
        """
        Создает смешанный слой для перехода.
        
        При морфинге - попиксельное смешивание.
        При несовпадении - прыжок новой картинки поверх старой снизу вверх.
        """
        t = transition.progress.value
        
        if transition.from_state is None:
            # нет исходного состояния, просто применяем альфу
            return self._apply_fade_in(transition.to_state.layer, t)

        # если ничего не поменялось, не дергаем слой
        if (
            transition._from_pixels is not None
            and transition._to_pixels is not None
            and transition._from_pixels.shape == transition._to_pixels.shape
            and np.isclose(transition._from_x, transition._to_x)
            and np.isclose(transition._from_y, transition._to_y)
            and transition.similarity > 0.985
        ):
            return transition.to_state.layer
        
        if transition.use_jump_transition:
            # прыжок для переходов между приложениями
            return self._blend_jump(transition, t)
        elif transition.use_morph:
            # попиксельный морфинг для похожих картинок
            return self._blend_morph(transition, t)
        else:
            # кроссфейд для непохожих частей лица
            return self._blend_crossfade(transition, t)
    
    def _apply_fade_in(self, layer, t: float):
        """Применяет плавное появление"""
        if isinstance(layer, SpriteLayer):
            # модифицируем альфа-канал
            pixels = np.frombuffer(layer.image, dtype=np.uint8).reshape(
                layer.sprite_height, layer.sprite_width, 4
            ).copy()
            pixels[:, :, 3] = (pixels[:, :, 3] * t).astype(np.uint8)
            
            return SpriteLayer(
                image=pixels.tobytes(),
                sprite_width=layer.sprite_width,
                sprite_height=layer.sprite_height,
                x=layer.x,
                y=layer.y
            )
        return layer
    
    def _blend_morph(self, transition: PartTransition, t: float) -> SpriteLayer:
        """Попиксельный морфинг между состояниями с интерполяцией координат"""
        from_pixels = transition._from_pixels
        to_pixels = transition._to_pixels
        
        if from_pixels is None or to_pixels is None:
            return transition.to_state.layer
        
        # косинус для плавности
        cos_t = (1.0 - np.cos(t * np.pi)) / 2.0
        src = from_pixels.astype(np.float32)
        dst = to_pixels.astype(np.float32)
        h, w = src.shape[:2]

        src_alpha = src[:, :, 3].astype(np.float32) / 255.0
        dst_alpha = dst[:, :, 3].astype(np.float32) / 255.0

        src_mask = src_alpha > 0.05
        dst_mask = dst_alpha > 0.05

        def _center_and_size(mask: np.ndarray, alpha: np.ndarray) -> tuple[np.ndarray, float, float]:
            if mask.sum() < 1.0:
                return np.array([w * 0.5, h * 0.5]), 1.0, 1.0
            ys, xs = np.nonzero(mask)
            weights = alpha[ys, xs]
            w_sum = float(weights.sum())
            if w_sum < 1e-5:
                return np.array([w * 0.5, h * 0.5]), 1.0, 1.0
            cx = float((xs * weights).sum() / w_sum)
            cy = float((ys * weights).sum() / w_sum)
            width = float(xs.max() - xs.min() + 1)
            height = float(ys.max() - ys.min() + 1)
            return np.array([cx, cy]), width, height

        center_src, w_src, h_src = _center_and_size(src_mask, src_alpha)
        center_dst, w_dst, h_dst = _center_and_size(dst_mask, dst_alpha)

        scale_x = np.clip(w_dst / max(1.0, w_src), 0.4, 2.5)
        scale_y = np.clip(h_dst / max(1.0, h_src), 0.4, 2.5)

        moved_rgb = np.zeros((h, w, 3), dtype=np.float32)
        alpha_acc = np.zeros((h, w), dtype=np.float32)

        ys, xs = np.nonzero(src_mask)
        if len(xs) > 0:
            alphas = src_alpha[ys, xs]

            tx = center_dst[0] + (xs - center_src[0]) * scale_x
            ty = center_dst[1] + (ys - center_src[1]) * scale_y

            cur_x = xs + (tx - xs) * cos_t
            cur_y = ys + (ty - ys) * cos_t

            x0 = np.floor(cur_x).astype(int)
            y0 = np.floor(cur_y).astype(int)
            x1 = x0 + 1
            y1 = y0 + 1

            wx = cur_x - x0
            wy = cur_y - y0

            weights = [
                ((1 - wx) * (1 - wy), x0, y0),
                ((1 - wx) * wy, x0, y1),
                (wx * (1 - wy), x1, y0),
                (wx * wy, x1, y1),
            ]

            src_rgb = src[ys, xs, :3]

            for w_part, x_part, y_part in weights:
                valid = (
                    (x_part >= 0)
                    & (x_part < w)
                    & (y_part >= 0)
                    & (y_part < h)
                )

                if not np.any(valid):
                    continue

                contrib = (alphas * w_part)[valid]
                xs_v = x_part[valid]
                ys_v = y_part[valid]

                np.add.at(alpha_acc, (ys_v, xs_v), contrib)
                for c in range(3):
                    np.add.at(moved_rgb[:, :, c], (ys_v, xs_v), src_rgb[valid, c] * contrib)

        warped_alpha = np.clip(alpha_acc, 0.0, 1.0)

        # премультиплированное смешивание, чтобы не темнело и не исчезало
        src_mix_alpha = warped_alpha * (1.0 - cos_t)
        dst_mix_alpha = dst_alpha * cos_t
        total_alpha = src_mix_alpha + dst_mix_alpha - src_mix_alpha * dst_mix_alpha

        premult_rgb = (dst[:, :, :3] * dst_mix_alpha[..., None]) + (moved_rgb * (1.0 - cos_t))
        safe_alpha = np.clip(total_alpha, 1e-5, None)
        final_rgb = premult_rgb / safe_alpha[..., None]
        final_rgb[total_alpha < 1e-5] = 0.0

        blended = np.zeros_like(dst)
        blended[:, :, :3] = np.clip(final_rgb, 0.0, 255.0)
        blended[:, :, 3] = np.clip(total_alpha * 255.0, 0.0, 255.0)
        blended = blended.astype(np.uint8)
        
        morph_x = transition._from_x + (transition._to_x - transition._from_x) * cos_t
        morph_y = transition._from_y + (transition._to_y - transition._from_y) * cos_t
        
        target_layer = transition.to_state.layer
        
        return SpriteLayer(
            image=blended.tobytes(),
            sprite_width=target_layer.sprite_width if hasattr(target_layer, 'sprite_width') else blended.shape[1],
            sprite_height=target_layer.sprite_height if hasattr(target_layer, 'sprite_height') else blended.shape[0],
            x=morph_x,
            y=morph_y
        )
    
    def _blend_crossfade(self, transition: PartTransition, t: float) -> SpriteLayer:
        """
        Плавный кроссфейд между двумя изображениями с интерполяцией координат.
        Старая картинка постепенно исчезает, новая появляется с косинусной интерполяцией.
        """
        from_pixels = transition._from_pixels
        to_pixels = transition._to_pixels
        
        if from_pixels is None:
            return transition.to_state.layer
        
        if to_pixels is None:
            return transition.from_state.layer
        
        # косинусная интерполяция для плавного начала/конца
        cos_t = (1.0 - np.cos(t * np.pi)) / 2.0
        from_alpha = 1.0 - cos_t
        to_alpha = cos_t
        
        # интерполируем координаты
        fade_x = transition._from_x + (transition._to_x - transition._from_x) * cos_t
        fade_y = transition._from_y + (transition._to_y - transition._from_y) * cos_t
        
        if from_pixels.shape == to_pixels.shape:
            # размеры совпадают - просто смешиваем
            blended = (
                from_pixels.astype(np.float32) * from_alpha +
                to_pixels.astype(np.float32) * to_alpha
            ).astype(np.uint8)
        else:
            # размеры разные - берем размер целевого
            h_to, w_to = to_pixels.shape[:2]
            blended = (to_pixels.astype(np.float32) * to_alpha).astype(np.uint8)
            
            # накладываем старую картинку в центр если она меньше
            h_from, w_from = from_pixels.shape[:2]
            if h_from <= h_to and w_from <= w_to:
                y_off = (h_to - h_from) // 2
                x_off = (w_to - w_from) // 2
                blended[y_off:y_off+h_from, x_off:x_off+w_from] += (
                    from_pixels.astype(np.float32) * from_alpha
                ).astype(np.uint8)
        
        target_layer = transition.to_state.layer
        
        return SpriteLayer(
            image=blended.tobytes(),
            sprite_width=target_layer.sprite_width if hasattr(target_layer, 'sprite_width') else blended.shape[1],
            sprite_height=target_layer.sprite_height if hasattr(target_layer, 'sprite_height') else blended.shape[0],
            x=fade_x,
            y=fade_y
        )
    
    def _blend_jump(self, transition: PartTransition, t: float) -> SpriteLayer:
        """
        Прыжок новой картинки поверх старой снизу вверх с плавным морфингом и интерполяцией координат.
        Используется для переходов между приложениями с красивым эффектом перетекания.
        """
        from_pixels = transition._from_pixels
        to_pixels = transition._to_pixels
        
        if from_pixels is None:
            return transition.to_state.layer
        
        if to_pixels is None:
            return transition.from_state.layer
        
        height, width = to_pixels.shape[:2]
        
        # косинусная интерполяция для плавного затухания старого
        cos_t = (1.0 - np.cos(t * np.pi)) / 2.0
        fade_out = 1.0 - cos_t
        
        # интерполируем координаты
        jump_x = transition._from_x + (transition._to_x - transition._from_x) * cos_t
        jump_y = transition._from_y + (transition._to_y - transition._from_y) * cos_t
        
        # создаем результат на основе старого изображения с затуханием
        if from_pixels.shape == to_pixels.shape:
            result = (from_pixels.astype(np.float32) * fade_out).astype(np.uint8)
        else:
            # если размеры разные, берем размер целевого
            result = np.zeros_like(to_pixels)
            # копируем старое в центр если возможно
            h_f, w_f = from_pixels.shape[:2]
            y_off = (height - h_f) // 2
            x_off = (width - w_f) // 2
            if y_off >= 0 and x_off >= 0:
                result[y_off:y_off+h_f, x_off:x_off+w_f] = (from_pixels.astype(np.float32) * fade_out).astype(np.uint8)
        
        # вычисляем текущую позицию Y для новой картинки (от height до 0)
        # косинусная функция для плавного движения
        cos_movement = (1.0 - np.cos((1.0 - t) * np.pi)) / 2.0
        current_y = int(cos_movement * height)
        
        # накладываем новое изображение со смещением
        if current_y < height:
            visible_h = height - current_y
            new_part = to_pixels[0:visible_h, :]
            
            # Маска для не-черных пикселей (RGB > 0)
            if new_part.shape[2] == 4:
                # Учитываем и альфу, и цвет (черный = прозрачный)
                mask = (new_part[:, :, 3] > 0) & np.any(new_part[:, :, :3] > 0, axis=2)
            else:
                mask = np.any(new_part[:, :, :3] > 0, axis=2)
            
            # Накладываем только там, где маска True
            target_area = result[current_y:height, :]
            target_area[mask] = new_part[mask]
            
        target_layer = transition.to_state.layer
        
        return SpriteLayer(
            image=result.tobytes(),
            sprite_width=target_layer.sprite_width if hasattr(target_layer, 'sprite_width') else width,
            sprite_height=target_layer.sprite_height if hasattr(target_layer, 'sprite_height') else height,
            x=jump_x,
            y=jump_y
        )

