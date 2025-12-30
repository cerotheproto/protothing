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
            raise ValueError(f"Эффект '{effect_name}' не найден")
        
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
