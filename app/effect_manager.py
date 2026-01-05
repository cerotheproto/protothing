from render.frame_description import WiggleEffect, DizzyEffect, Effect, RainbowEffect, ShakeEffect, ColorOverrideEffect
import uuid

# класс для хранения и управления эффектами из апи
class EffectManager:
    def __init__(self):
        self.effects: list[Effect] = []
        self._available_effects = {
            "Wiggle": WiggleEffect,
            "Dizzy": DizzyEffect,
            "Rainbow": RainbowEffect,
            "Shake": ShakeEffect,
            "ColorOverride": ColorOverrideEffect,
        }
        self._layers_cache: list = []  # кеш слоев для cleanup

    def add_effect_by_name(self, effect_name: str, **kwargs) -> Effect:
        """Добавляет эффект по имени с параметрами"""
        effect_class = self._available_effects.get(effect_name)
        if effect_class is None:
            raise ValueError(f"Effect '{effect_name}' not found")
        
        effect = effect_class(**kwargs)
        effect.id = str(uuid.uuid4())
        self.effects.append(effect)
        return effect
    
    def add_effect(self, effect: Effect) -> None:
        """Добавляет готовый эффект в менеджер"""
        if not effect.id:
            effect.id = str(uuid.uuid4())
        self.effects.append(effect)

    def remove_effect(self, effect: Effect) -> bool:
        """Удаляет эффект из менеджера"""
        if effect in self.effects:
            # Если эффект поддерживает плавное выключение, запускаем его
            if hasattr(effect, '_is_stopping') and not effect._is_stopping:
                effect._is_stopping = True
                return True
            
            effect.cleanup(self._layers_cache)
            self.effects.remove(effect)
            return True
        return False
    
    def remove_effect_by_id(self, effect_id: str) -> bool:
        """Удаляет эффект по ID"""
        for effect in self.effects:
            if effect.id == effect_id:
                # Если эффект поддерживает плавное выключение, запускаем его
                if hasattr(effect, '_is_stopping') and not effect._is_stopping:
                    effect._is_stopping = True
                    return True

                effect.cleanup(self._layers_cache)
                self.effects.remove(effect)
                return True
        return False

    def clear_effects(self) -> None:
        """Очищает все эффекты"""
        for effect in self.effects:
            # Если эффект поддерживает плавное выключение, запускаем его
            if hasattr(effect, '_is_stopping') and not effect._is_stopping:
                effect._is_stopping = True
                continue
            effect.cleanup(self._layers_cache)
        
        # Удаляем только те, которые не перешли в режим остановки
        self.effects = [e for e in self.effects if hasattr(e, '_is_stopping') and e._is_stopping]
    
    def is_clearing(self) -> bool:
        """Проверяет, есть ли эффекты в процессе очистки"""
        return any(hasattr(e, '_is_stopping') and e._is_stopping for e in self.effects)

    def get_available_effects(self) -> list[str]:
        """Возвращает список доступных типов эффектов"""
        return list(self._available_effects.keys())
    
    def get_effects(self) -> list[Effect]:
        """Возвращает список активных эффектов"""
        # Удаляем завершенные эффекты
        finished_effects = [e for e in self.effects if hasattr(e, '_state') and e._state == 'finished']
        for effect in finished_effects:
            effect.cleanup(self._layers_cache)
            self.effects.remove(effect)
            
        return self.effects.copy()
    
    def update_layers_cache(self, layers: list) -> None:
        """Обновляет кеш слоев для cleanup"""
        self._layers_cache = layers

    def save_effect_params(self) -> list[tuple[str, dict]]:
        """Сохраняет параметры текущих эффектов без их состояния"""
        effect_params = []
        for effect in self.effects:
            effect_name = None
            params = {}
            
            # Find effect name and extract params
            for name, effect_class in self._available_effects.items():
                if isinstance(effect, effect_class):
                    effect_name = name
                    break
            
            if effect_name is None:
                continue
            
            # Get effect parameters (excluding private fields and id)
            import dataclasses
            for field in dataclasses.fields(effect):
                if field.name.startswith('_') or field.name == 'id':
                    continue
                value = getattr(effect, field.name)
                # Skip numpy arrays and complex objects
                if not isinstance(value, (list, dict)):
                    params[field.name] = value
            
            effect_params.append((effect_name, params))
        
        return effect_params
    
    def restore_effects(self, effect_params: list[tuple[str, dict]]) -> None:
        """Восстанавливает эффекты по сохраненным параметрам"""
        for effect_name, params in effect_params:
            try:
                self.add_effect_by_name(effect_name, **params)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to restore effect '{effect_name}': {e}")
