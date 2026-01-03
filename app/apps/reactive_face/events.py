from typing import TYPE_CHECKING
from models.app_contract import Event, Query, QueryResult
import random
import logging
logger = logging.getLogger(__name__)
if TYPE_CHECKING:
    from apps.reactive_face.app import ReactiveFaceApp

class ChangeFaceState(Event):
    """Изменяет состояние части лица"""
    part_type: str  # тип части лица, например "eyes", "mouth"
    new_state: str  # новое состояние, например "happy", "sad"

class ReloadMetadata(Event):
    """Перезагружает метаданные частей лица из хранилища"""
    pass

class SetBlinking(Event):
    """Переключает моргание глаз"""
    enabled: bool

class SetAudioReactive(Event):
    """Переключает аудиореактивную анимацию рта"""
    enabled: bool


class OverrideFacePart(Event):
    """Меняет часть лица на указанное состояние, игнорируя текущий пресет"""
    part_type: str
    ref: str
    state: str = "default"

class ChangePreset(Event):
    """Меняет текущий пресет"""
    preset_name: str

class GetFaceState(Query):
    """Получить текущее состояние лица"""
    pass

class FaceStateResult(QueryResult):
    preset: str
    presets: list[str]
    states: dict[str, dict[str, str]]  # тип части лица -> ссылка, состояние
    audio_reactive: bool
    blinking: bool
    available_parts: dict[str, list[dict]]  # тип части лица -> список доступных частей лица с их метаданными


def handle_events(self: "ReactiveFaceApp", dt: float, events: list[Event]):
    self._ensure_initialized()
    for event in events:
        if isinstance(event, ChangeFaceState):
            if event.part_type in self.current_states:
                old_state = self.current_states[event.part_type]
                new_state = event.new_state
                
                if old_state != new_state:
                    self.current_states[event.part_type] = new_state
                    
                    # запускаем переход для этой части
                    if self.current_preset and event.part_type in self.current_preset.parts:
                        ref = self.current_preset.parts[event.part_type][0]
                        self._start_part_transition(
                            event.part_type, ref, old_state, ref, new_state
                        )
        elif isinstance(event, ReloadMetadata):
            self.face_parts_cache.reload_metadata()
            if self.current_preset:
                self._load_preset(self.current_preset.name)
        elif isinstance(event, OverrideFacePart):
            self._override_face_part(event.part_type, event.ref, event.state)
        elif isinstance(event, ChangePreset):
            self._load_preset(event.preset_name)
        elif isinstance(event, SetBlinking):
            self.blink_enabled = event.enabled
            # Если моргание выключено и мы находимся в состоянии моргания,
            # возвращаемся в дефолтное состояние
            if not event.enabled and self.blink_state is not None:
                if self.current_preset and "eye" in self.current_preset.parts:
                    eye_ref = self.current_preset.parts["eye"][0]
                    eye_part = self.face_parts_cache.get_part("eye", eye_ref)
                    self.current_states["eye"] = eye_part.default_state
                    self.blink_state = None
                    self.blink_prev_eye_state = None
                    self.time_to_next_blink = random.uniform(3, 5)
                    self.blink_elapsed_time = 0.0
        elif isinstance(event, SetAudioReactive):
            self.audio_enabled = event.enabled
            if event.enabled:
                try:
                    self.audio_processor.start()
                except Exception as e:
                    logger.error(f"Error starting audio processor: {e}")
                    self.audio_enabled = False
            else:
                try:
                    self.audio_processor.stop()
                except Exception as e:
                    logger.error(f"Error stopping audio processor: {e}")

def get_events(self) -> list[type[Event]]:
    return [ChangeFaceState, ReloadMetadata, OverrideFacePart, ChangePreset, SetBlinking, SetAudioReactive]

def get_queries(self) -> list[type[Query]]:
    return [GetFaceState]

def handle_queries(self: "ReactiveFaceApp", query: Query) -> QueryResult:
    """Обрабатывает запросы приложения"""
    if isinstance(query, GetFaceState):
        self._ensure_initialized()
        return FaceStateResult(
            preset=self.current_preset.name if self.current_preset else "",
            presets=self.face_parts_cache.get_all_presets(),
            states={
                part_type: {
                    "ref": self.current_preset.parts[part_type][0] if self.current_preset and part_type in self.current_preset.parts else "",
                    "state": state
                }
                for part_type, state in self.current_states.items()
            },
            available_parts=self.face_parts_cache.get_all_parts_metadata(),
            audio_reactive=self.audio_enabled,
            blinking=self.blink_enabled
        )
    raise NotImplementedError(f"Query {type(query).__name__} is not supported")