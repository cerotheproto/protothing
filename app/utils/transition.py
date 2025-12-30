"""
Утилиты для плавных переходов и интерполяций.
Адаптация логики из ProtoTracer (EasyEaseAnimator, DampedSpring, RampFilter).
"""

import numpy as np
from enum import Enum
from dataclasses import dataclass, field


class InterpolationMethod(Enum):
    """Методы интерполяции"""
    LINEAR = "linear"
    COSINE = "cosine"
    BOUNCE = "bounce"
    OVERSHOOT = "overshoot"


@dataclass
class DampedSpring:
    """
    Затухающая пружина для плавных переходов с инерцией.
    Позволяет значению перелетать цель и возвращаться (overshoot).
    """
    spring_constant: float = 15.0
    damping: float = 5.0
    _position: float = field(default=0.0, repr=False)
    _velocity: float = field(default=0.0, repr=False)
    
    def calculate(self, target: float, dt: float) -> float:
        """Рассчитывает новое положение пружины"""
        if dt <= 0 or dt > 2.0:
            return self._position
        
        # сила пружины + демпфирование
        spring_force = -self.spring_constant * (self._position - target)
        damping_force = -self.damping * self._velocity
        force = spring_force + damping_force
        
        self._velocity += force * dt
        self._position += self._velocity * dt
        
        return self._position
    
    def reset(self, position: float = 0.0):
        """Сбрасывает состояние пружины"""
        self._position = position
        self._velocity = 0.0
    
    @property
    def position(self) -> float:
        return self._position


@dataclass 
class RampFilter:
    """
    Фильтр плавного нарастания значения.
    Изменяет значение с фиксированным шагом за кадр.
    """
    frames: int = 15  # количество кадров для полного перехода
    _value: float = field(default=0.0, repr=False)
    
    @property
    def increment(self) -> float:
        return 1.0 / max(1, self.frames)
    
    def filter(self, target: float) -> float:
        """Фильтрует значение, приближая к цели"""
        diff = target - self._value
        
        if abs(diff) < self.increment / 2.0:
            return self._value
        
        if diff > 0:
            self._value = min(self._value + self.increment, 1.0)
        else:
            self._value = max(self._value - self.increment, 0.0)
        
        return self._value
    
    def reset(self, value: float = 0.0):
        """Сбрасывает значение"""
        self._value = np.clip(value, 0.0, 1.0)
    
    @property
    def value(self) -> float:
        return self._value


def cosine_interpolation(start: float, end: float, t: float) -> float:
    """Косинусная интерполяция (плавное начало и конец)"""
    t = np.clip(t, 0.0, 1.0)
    cos_t = (1.0 - np.cos(t * np.pi)) / 2.0
    return start + (end - start) * cos_t


def bounce_interpolation(start: float, end: float, t: float) -> float:
    """Интерполяция с отскоком"""
    t = np.clip(t, 0.0, 1.0)
    
    if t < 0.7:
        # основное движение
        bounce_t = t / 0.7
        cos_t = (1.0 - np.cos(bounce_t * np.pi)) / 2.0
        return start + (end - start) * cos_t
    else:
        # отскок
        bounce_t = (t - 0.7) / 0.3
        overshoot = 0.1 * np.sin(bounce_t * np.pi)
        return end + (end - start) * overshoot


def lerp(start: float, end: float, t: float) -> float:
    """Линейная интерполяция"""
    t = np.clip(t, 0.0, 1.0)
    return start + (end - start) * t


def lerp_array(start: np.ndarray, end: np.ndarray, t: float) -> np.ndarray:
    """Линейная интерполяция массивов"""
    t = np.clip(t, 0.0, 1.0)
    return start + (end - start) * t


def interpolate(start: float, end: float, t: float, method: InterpolationMethod) -> float:
    """Интерполирует значение выбранным методом"""
    if method == InterpolationMethod.LINEAR:
        return lerp(start, end, t)
    elif method == InterpolationMethod.COSINE:
        return cosine_interpolation(start, end, t)
    elif method == InterpolationMethod.BOUNCE:
        return bounce_interpolation(start, end, t)
    else:
        return lerp(start, end, t)


@dataclass
class AnimatedParameter:
    """
    Анимированный параметр с плавным переходом.
    Аналог EasyEaseAnimator из ProtoTracer для одного параметра.
    """
    frames: int = 15  # длительность перехода в кадрах
    method: InterpolationMethod = InterpolationMethod.COSINE
    spring_constant: float = 15.0
    damping: float = 5.0
    
    _ramp: RampFilter = field(default=None, repr=False)
    _spring: DampedSpring = field(default=None, repr=False)
    _basis: float = field(default=0.0, repr=False)
    _goal: float = field(default=1.0, repr=False)
    _current: float = field(default=0.0, repr=False)
    _target: float = field(default=0.0, repr=False)
    
    def __post_init__(self):
        self._ramp = RampFilter(frames=self.frames)
        self._spring = DampedSpring(
            spring_constant=self.spring_constant,
            damping=self.damping
        )
    
    def set_target(self, target: float):
        """Устанавливает целевое значение"""
        self._target = np.clip(target, self._basis, self._goal)
    
    def update(self, dt: float) -> float:
        """Обновляет значение и возвращает текущее"""
        # нормализуем цель в диапазон [0, 1]
        normalized_target = (self._target - self._basis) / max(0.0001, self._goal - self._basis)
        
        if self.method == InterpolationMethod.OVERSHOOT:
            self._current = self._spring.calculate(normalized_target, dt)
        else:
            filtered = self._ramp.filter(normalized_target)
            self._current = interpolate(0.0, 1.0, filtered, self.method)
        
        # денормализуем обратно
        return self._basis + (self._goal - self._basis) * self._current
    
    def reset(self, value: float = 0.0):
        """Сбрасывает параметр"""
        normalized = (value - self._basis) / max(0.0001, self._goal - self._basis)
        self._ramp.reset(normalized)
        self._spring.reset(normalized)
        self._current = normalized
        self._target = value
    
    @property
    def value(self) -> float:
        """Текущее значение в диапазоне [basis, goal]"""
        return self._basis + (self._goal - self._basis) * self._current


def calculate_image_similarity(img1: np.ndarray, img2: np.ndarray) -> float:
    """
    Вычисляет схожесть двух изображений на основе топологии линий.
    Сравнивает структуру, центр масс и количество активных пикселей.
    Возвращает значение от 0 (полностью различны) до 1 (идентичны).
    """
    if img1.shape != img2.shape:
        return 0.0
    
    # Переводим в ч/б для сравнения форм, а не цветов
    if len(img1.shape) == 3:
        if img1.shape[2] == 4: # RGBA
            # учитываем альфу если она есть
            gray1 = (0.299 * img1[:,:,0] + 0.587 * img1[:,:,1] + 0.114 * img1[:,:,2]) * (img1[:,:,3] / 255.0)
            gray2 = (0.299 * img2[:,:,0] + 0.587 * img2[:,:,1] + 0.114 * img2[:,:,2]) * (img2[:,:,3] / 255.0)
        else: # RGB
            gray1 = 0.299 * img1[:,:,0] + 0.587 * img1[:,:,1] + 0.114 * img1[:,:,2]
            gray2 = 0.299 * img2[:,:,0] + 0.587 * img2[:,:,1] + 0.114 * img2[:,:,2]
    else:
        gray1 = img1
        gray2 = img2

    # нормализуем к float и binarize
    g1_f = (gray1.astype(np.float32) / 255.0) > 0.5
    g2_f = (gray2.astype(np.float32) / 255.0) > 0.5
    
    # Пиксельное совпадение (IoU - Intersection over Union)
    intersection = np.sum(g1_f & g2_f)
    union = np.sum(g1_f | g2_f)
    
    if union == 0:
        # обе пустые
        return 1.0
    
    iou = intersection / union
    
    # Сравнение размера (количества активных пикселей)
    count1 = np.sum(g1_f)
    count2 = np.sum(g2_f)
    max_count = max(count1, count2)
    
    if max_count == 0:
        size_similarity = 1.0
    else:
        min_count = min(count1, count2)
        size_similarity = min_count / max_count
    
    # Сравнение центра масс
    if count1 > 0 and count2 > 0:
        y1, x1 = np.where(g1_f)
        center1 = np.array([np.mean(x1), np.mean(y1)])
        
        y2, x2 = np.where(g2_f)
        center2 = np.array([np.mean(x2), np.mean(y2)])
        
        # расстояние между центрами в пикселях
        distance = np.linalg.norm(center1 - center2)
        # диагональ изображения
        diag = np.sqrt(img1.shape[0]**2 + img1.shape[1]**2)
        # штраф за расстояние (максимум 0.3)
        distance_penalty = min(0.3, (distance / diag) * 0.5)
    else:
        distance_penalty = 0.3 if count1 != count2 else 0.0
    
    # Комбинированная метрика
    # IoU дает основную оценку, size_similarity и center уточняют
    similarity = iou * 0.7 + size_similarity * 0.2 - distance_penalty * 0.1
    
    return float(np.clip(similarity, 0.0, 1.0))


def is_bright_to_dark(img1: np.ndarray, img2: np.ndarray) -> bool:
    """
    Проверяет, является ли переход переходом от яркого/сложного фона к темному (черному).
    """
    if img1 is None or img2 is None:
        return False
        
    # Средняя яркость
    def get_brightness(img):
        if len(img.shape) == 3:
            # Берем только RGB, игнорируем альфу для оценки яркости фона
            return np.mean(img[:,:,:3]) / 255.0
        return np.mean(img) / 255.0
        
    b1 = get_brightness(img1)
    b2 = get_brightness(img2)
    
    # Если старое изображение яркое (>0.4), а новое темное (<0.1)
    return b1 > 0.4 and b2 < 0.1
