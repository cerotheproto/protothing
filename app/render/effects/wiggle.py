import time
import numpy as np
from numpy.random import default_rng
from render.frame_description import WiggleEffect, SpriteLayer, AnimatedSpriteLayer


SPRITE_TYPES = (SpriteLayer, AnimatedSpriteLayer)


def cleanup_wiggle_effect(effect: WiggleEffect, layers: list) -> None:
    """Восстанавливает исходные позиции спрайтов после удаления эффекта"""
    sprite_layers = [layer for layer in layers if isinstance(layer, SPRITE_TYPES)]
    
    for layer in sprite_layers:
        layer_id = id(layer)
        state = effect._sprite_states.get(layer_id)
        
        if state is not None:
            # Восстанавливаем базовую позицию
            base = state["base"]
            layer.x = float(base[0])
            layer.y = float(base[1])
    
    # Очищаем состояния
    effect._sprite_states.clear()


def wiggle_effect(layers: list, effect: WiggleEffect, dt: float) -> None:
    """Применяет эффект плавного дрожания ко всем спрайтам согласованно"""
    sprite_layers = [layer for layer in layers if isinstance(layer, SPRITE_TYPES)]
    if not sprite_layers or effect.amplitude <= 0.0:
        return

    # Управление временем и состоянием симуляции
    # Используем time.monotonic() для определения, является ли вызов повторным в рамках одного кадра
    now = time.monotonic()
    last_exec = getattr(effect, "_last_exec_time", 0.0)
    # Если прошло очень мало времени (менее 2мс), считаем что это тот же кадр (например, второй дисплей)
    is_same_frame = (now - last_exec) < 0.002
    
    if not is_same_frame:
        # Новый кадр: продвигаем внутреннее время и обновляем RNG
        effect._last_exec_time = now
        effect._internal_time = getattr(effect, "_internal_time", 0.0) + dt
        effect._last_dt = dt
        
        rng = _ensure_rng(effect)
        
        # Обновляем глобальное направление дрейфа
        direction = _update_direction(effect, dt, rng)
        if direction is None:
            direction = np.array([1.0, 0.0], dtype=np.float32)

        # Обновляем глобальное смещение с мягким колебанием
        _update_global_offset(effect, direction, dt, rng)
        
        # Очищаем старые состояния (с таймаутом, чтобы не удалять слои второго дисплея)
        _cleanup_stale_states(effect)

    # Применяем смещение ко всем слоям
    # Передаем internal_time, чтобы слой обновлялся только один раз за логический тик
    current_internal_time = getattr(effect, "_internal_time", 0.0)
    step_dt = getattr(effect, "_last_dt", dt)
    
    for layer in sprite_layers:
        _apply_to_layer(layer, effect, current_internal_time, step_dt)


def _ensure_rng(effect: WiggleEffect):
    if effect._rng_state is None:
        effect._rng_state = default_rng(effect.seed)
    return effect._rng_state


def _cleanup_stale_states(effect: WiggleEffect) -> None:
    """Удаляем состояния, которые не обновлялись более 1 секунды"""
    current_time = getattr(effect, "_internal_time", 0.0)
    timeout = 1.0  # секунды
    
    # Собираем ID для удаления
    to_remove = []
    for layer_id, state in effect._sprite_states.items():
        last_seen = state.get("last_seen", current_time) # Если нет last_seen, считаем новым
        if current_time - last_seen > timeout:
            to_remove.append(layer_id)
            
    for layer_id in to_remove:
        effect._sprite_states.pop(layer_id, None)


def _update_direction(effect: WiggleEffect, dt: float, rng) -> np.ndarray | None:
    if effect._direction is None:
        effect._direction = _random_unit_vector(rng)

    if effect._direction_target is None:
        effect._direction_target = _deviate_direction(effect._direction, rng, max_angle=30.0)
        effect._direction_duration = _choose_direction_interval(effect, rng)
        effect._direction_elapsed = 0.0

    effect._direction_elapsed += dt
    duration = max(effect._direction_duration, 1e-3)
    progress = min(effect._direction_elapsed / duration, 1.0)

    blended = effect._direction * (1.0 - progress) + effect._direction_target * progress
    norm = np.linalg.norm(blended)
    if norm < 1e-5:
        blended = effect._direction_target
        norm = np.linalg.norm(blended)
    
    if norm < 1e-5:
        return None

    current = blended / norm

    if progress >= 1.0:
        effect._direction = current
        effect._direction_target = _deviate_direction(effect._direction, rng, max_angle=30.0)
        effect._direction_duration = _choose_direction_interval(effect, rng)
        effect._direction_elapsed = 0.0

    return current


def _update_global_offset(effect: WiggleEffect, direction: np.ndarray, dt: float, rng) -> None:
    _ensure_wave_state(effect, rng)
    _update_amplitude_modulation(effect, dt, rng)
    _update_wander(effect, dt, rng)

    perp = _perpendicular(direction)
    base_amp = max(effect.amplitude, 0.0) * effect._amp_mod
    lateral_amp = base_amp * max(effect.lateral_ratio, 0.0) * 0.7

    effect._phase_main += dt * effect._freq_main * (2.0 * np.pi)
    effect._phase_lateral += dt * effect._freq_lateral * (2.0 * np.pi)

    main_wave = np.sin(effect._phase_main) * base_amp
    lateral_wave = np.sin(effect._phase_lateral) * lateral_amp

    offset = effect._wander_center + direction * main_wave + perp * lateral_wave

    max_len = max(effect.amplitude * 1.1, 1e-3)
    norm = np.linalg.norm(offset)
    if norm > max_len:
        offset = offset / norm * max_len

    effect._current_offset = offset.astype(np.float32)


def _ensure_wave_state(effect: WiggleEffect, rng) -> None:
    if hasattr(effect, "_phase_main"):
        return
    effect._phase_main = float(rng.uniform(0.0, 2.0 * np.pi))
    effect._phase_lateral = float(rng.uniform(0.0, 2.0 * np.pi))
    effect._freq_main = float(rng.uniform(0.16, 0.24))
    effect._freq_lateral = float(rng.uniform(0.22, 0.32))
    effect._amp_mod = float(rng.uniform(0.75, 1.0))
    effect._amp_mod_target = effect._amp_mod
    effect._amp_mod_start = effect._amp_mod
    effect._amp_mod_timer = 0.0
    effect._amp_mod_duration = float(rng.uniform(2.5, 4.5))
    effect._wander_center = np.zeros(2, dtype=np.float32)
    effect._wander_velocity = np.zeros(2, dtype=np.float32)


def _update_amplitude_modulation(effect: WiggleEffect, dt: float, rng) -> None:
    effect._amp_mod_timer += dt
    duration = max(effect._amp_mod_duration, 1e-3)
    progress = min(effect._amp_mod_timer / duration, 1.0)
    eased = _smoothstep(progress)
    effect._amp_mod = effect._amp_mod_start * (1.0 - eased) + effect._amp_mod_target * eased

    if progress >= 1.0:
        effect._amp_mod_start = effect._amp_mod
        effect._amp_mod_target = float(rng.uniform(0.7, 1.0))
        effect._amp_mod_duration = float(rng.uniform(2.5, 4.5))
        effect._amp_mod_timer = 0.0


def _update_wander(effect: WiggleEffect, dt: float, rng) -> None:
    jitter = rng.normal(scale=0.45, size=2).astype(np.float32)
    accel = jitter * max(effect.amplitude, 0.1) * 0.25
    damping = 1.6

    effect._wander_velocity += (accel - effect._wander_velocity * damping) * dt
    effect._wander_center += effect._wander_velocity * dt

    limit = max(effect.amplitude * 0.6, 0.1)
    norm = np.linalg.norm(effect._wander_center)
    if norm > limit:
        effect._wander_center = effect._wander_center / norm * limit


def _apply_to_layer(layer: SpriteLayer | AnimatedSpriteLayer, effect: WiggleEffect, current_time: float, dt: float) -> None:
    layer_id = id(layer)
    state = effect._sprite_states.get(layer_id)
    
    # Инициализация состояния слоя
    if state is None:
        rng = _ensure_rng(effect)
        base = np.array([layer.x, layer.y], dtype=np.float32)
        local_scale = max(effect.amplitude, 1.0)
        state = {
            "base": base,
            "last_applied": base.copy(),
            "local_offset": np.zeros(2, dtype=np.float32),
            "local_target": _random_unit_vector(rng) * rng.uniform(0.12, 0.35) * local_scale,
            "local_duration": rng.uniform(1.8, 3.2),
            "local_elapsed": 0.0,
            "initialized": False,
            "last_seen": current_time,
            "last_update_time": -1.0
        }
        effect._sprite_states[layer_id] = state

    # Обновляем метку времени (для cleanup)
    state["last_seen"] = current_time

    # Синхронизация базы (если слой переместили извне)
    current_pos = np.array([layer.x, layer.y], dtype=np.float32)
    
    if state["initialized"]:
        last_applied = state["last_applied"]
        if not np.allclose(current_pos, last_applied, atol=1e-4):
            # Слой переместился не нами -> обновляем базу
            state["base"] = current_pos.copy()
    
    # Проверяем, нужно ли обновлять слой в этом кадре
    should_update_local = (state.get("last_update_time", -1.0) != current_time)
    
    if should_update_local:
        state["last_update_time"] = current_time
        
        # Обновляем локальное смещение для каждого спрайта
        state["local_elapsed"] += dt
        duration = max(state["local_duration"], 1e-3)
        progress = state["local_elapsed"] / duration
        
        if progress >= 1.0:
            rng = _ensure_rng(effect)
            local_scale = max(effect.amplitude, 1.0)
            state["local_target"] = _random_unit_vector(rng) * rng.uniform(0.12, 0.35) * local_scale
            state["local_duration"] = rng.uniform(1.8, 3.2)
            state["local_elapsed"] = 0.0
            progress = 0.0
        
        # Интерполируем локальное смещение
        eased = _smoothstep(min(progress, 1.0))
        state["local_offset"] = state["local_target"] * eased
    
    # Применяем глобальное + локальное смещение
    base_pos = state["base"]
    new_pos = base_pos + effect._current_offset + state["local_offset"]
    
    layer.x = float(new_pos[0])
    layer.y = float(new_pos[1])
    
    state["last_applied"] = np.array([layer.x, layer.y], dtype=np.float32)
    state["initialized"] = True


def _choose_direction_interval(effect: WiggleEffect, rng) -> float:
    base_min = max(1.4, min(effect.direction_interval_min, effect.direction_interval_max))
    base_max = max(base_min + 0.6, max(effect.direction_interval_min, effect.direction_interval_max) * 1.2)
    return float(rng.uniform(base_min, base_max))


def _random_unit_vector(rng) -> np.ndarray:
    vec = rng.normal(size=2)
    norm = np.linalg.norm(vec)
    if norm < 1e-6:
        return np.array([1.0, 0.0], dtype=np.float32)
    return (vec / norm).astype(np.float32)


def _deviate_direction(current: np.ndarray, rng, max_angle: float = 45.0) -> np.ndarray:
    """Отклоняет направление на случайный угол в пределах max_angle градусов"""
    # Переводим градусы в радианы
    max_rad = np.radians(max_angle)
    
    # Выбираем случайный угол отклонения
    angle_offset = rng.uniform(-max_rad, max_rad)
    
    # Получаем угол текущего направления
    current_angle = np.arctan2(current[1], current[0])
    new_angle = current_angle + angle_offset
    
    # Преобразуем обратно в вектор
    new_direction = np.array([
        np.cos(new_angle),
        np.sin(new_angle)
    ], dtype=np.float32)
    
    return new_direction


def _perpendicular(direction: np.ndarray) -> np.ndarray:
    perp = np.array([-direction[1], direction[0]], dtype=np.float32)
    norm = np.linalg.norm(perp)
    if norm < 1e-6:
        return np.array([0.0, 1.0], dtype=np.float32)
    return perp / norm


def _smoothstep(t: float) -> float:
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)
