from apps.base import BaseApp
from models.app_contract import Event, Query, QueryResult
from apps.reactive_face.face_parts import FacePartsCache, FacePreset
from transition_manager import TransitionManager
from render.frame_description import FrameDescription
import dependencies
from .events import handle_events, get_events as imported_get_events, get_queries as imported_get_queries, handle_queries
from utils.audio_processor import AudioProcessor
from display_manager import MirrorMode
import random
import logging
logger = logging.getLogger(__name__)
class ReactiveFaceApp(BaseApp):
    def __init__(self):
        super().__init__()
        self.name = "reactive_face"

        # регистрируем события
        self.get_events = imported_get_events.__get__(self)
        self.get_queries = imported_get_queries.__get__(self)
        
        # Кеш для загрузки частей лица
        self.face_parts_cache = FacePartsCache()
        
        # Текущий пресет и состояния
        self.current_preset: FacePreset | None = None
        self.current_states: dict[str, str] = {}  # тип -> состояние
        
        # Флаг инициализации
        self._initialized = False
        
        # Время до следующего моргания
        self.time_to_next_blink = random.uniform(3, 5)
        self.blink_elapsed_time = 0.0
        
        # Состояние моргания: None (ждем), "blinking" (моргаем)
        self.blink_state = None
        self.blink_duration = 0.0
        self.blink_prev_eye_state = None
        
        # Аудиопроцессор для анимации речи
        self.audio_processor = AudioProcessor(sample_rate=16000, chunk_size=512, smoothing_frames=3)
        self.audio_enabled = False

        self.blink_enabled = False
        
        # Менеджер переходов для частей лица
        self.transition_manager = TransitionManager()
        
        # Предыдущие состояния для отслеживания изменений
        self._prev_states: dict[str, str] = {}
        self._prev_preset_parts: dict[str, tuple[str, str]] = {}
    
    def start(self):
        # reactive_face is only app that needs display mirroring
        from dependencies import display_manager

        display_manager.set_mirror_mode(MirrorMode.RIGHT)
        super().start()

    def stop(self):
        from dependencies import display_manager
        logger.info("Restoring display mirror mode to NONE")
        display_manager.set_mirror_mode(MirrorMode.NONE)
        if self.audio_processor:
            self.audio_processor.stop()
        super().stop()   

    def _ensure_initialized(self):
        """Ленивая инициализация с загруженным конфигом"""
        if self._initialized:
            return
        
        default_preset = dependencies.config.get().reactive_face.default_preset
        self._load_preset(default_preset)
        self._initialized = True
        
        # Запускаем аудиопроцессор только если рот анимированный
        try:
            mouth_part = self.face_parts_cache.get_part("mouth", self.current_preset.parts["mouth"][0])
            if mouth_part.animated:
                self.audio_processor.start()
                self.audio_enabled = True
        except Exception as e:
            logger.error(f"Error initializing audio: {e}")
            self.audio_enabled = False

    def _load_preset(self, preset_name: str):
        """Загружает пресет и устанавливает текущее состояние"""
        old_preset = self.current_preset
        old_states = self.current_states.copy()
        
        self.current_preset = self.face_parts_cache.get_preset(preset_name)
        self.current_states = {
            part_type: state 
            for part_type, (ref, state) in self.current_preset.parts.items()
        }
        
        # запускаем переходы для всех изменившихся частей
        if old_preset is not None:
            self._start_transitions_for_changed_parts(old_preset, old_states)

    def _override_face_part(self, part_type: str, ref: str, state: str):
        """Меняет часть лица на указанное состояние, игнорируя текущий пресет"""
        face_part = self.face_parts_cache.get_part(part_type, ref)
        if face_part and self.current_preset:
            old_ref, old_state = self.current_preset.parts.get(part_type, (None, None))
            
            # запускаем переход если изменилось
            if old_ref is not None and (old_ref != ref or old_state != state):
                self._start_part_transition(part_type, old_ref, old_state, ref, state)
            
            self.current_preset.parts[part_type] = (ref, state)
            self.current_states[part_type] = state
    
    def _start_transitions_for_changed_parts(
        self, 
        old_preset: FacePreset, 
        old_states: dict[str, str]
    ):
        """Запускает переходы для всех изменившихся частей"""
        for part_type, (new_ref, new_default_state) in self.current_preset.parts.items():
            new_state = self.current_states.get(part_type, new_default_state)
            
            old_ref, old_default_state = old_preset.parts.get(part_type, (None, None))
            old_state = old_states.get(part_type, old_default_state)
            
            # если часть изменилась - запускаем переход
            if old_ref != new_ref or old_state != new_state:
                self._start_part_transition(part_type, old_ref, old_state, new_ref, new_state)
    
    def _start_part_transition(
        self,
        part_type: str,
        old_ref: str | None,
        old_state: str | None,
        new_ref: str,
        new_state: str
    ):
        """Запускает переход для одной части лица"""
        from_state = None
        if old_ref and old_state:
            try:
                old_part = self.face_parts_cache.get_part(part_type, old_ref)
                from_state = old_part.get_state(old_state)
            except Exception:
                pass
        
        try:
            new_part = self.face_parts_cache.get_part(part_type, new_ref)
            to_state = new_part.get_state(new_state)
            
            self.transition_manager.start_transition(
                part_type=part_type,
                from_state=from_state,
                to_state=to_state
            )
        except Exception as e:
            logger.error(f"Error starting transition for {part_type}: {e}")

    def reload_metadata(self):
        """Перезагружает метаданные частей лица"""
        self.face_parts_cache.reload_metadata()
        if self.current_preset:
            self._load_preset(self.current_preset.name)

    def _start_blink(self):
        """Начинает анимацию моргания"""
        if not self.current_preset or "eye" not in self.current_preset.parts:
            return
        
        if self.blink_state is not None:
            return
        
        # Получаем часть лица для проверки наличия состояния blink
        face_part = self.face_parts_cache.get_part("eye", self.current_preset.parts["eye"][0])
        
        # Проверяем наличие состояния blink и что активный дефолтный стейт - open
        if "blink" not in face_part.states or face_part.default_state != "open":
            return
        
        # Сохраняем текущее состояние глаз
        self.blink_prev_eye_state = self.current_states.get("eye", "default")
        
        # Переключаемся на моргание
        self.current_states["eye"] = "blink"
        self.blink_state = "blinking"
        self.blink_duration = 0.0
        
        # Получаем длительность анимации моргания
        part_state = face_part.get_state("blink")
        
        from render.frame_description import AnimatedSpriteLayer
        if isinstance(part_state.layer, AnimatedSpriteLayer):
            # Сбрасываем анимацию на начало
            part_state.layer.current_frame = 0
            part_state.layer.elapsed_time = 0.0
    
    def _update_blink(self, dt: float):
        """Обновляет состояние моргания"""
        if self.blink_state == "blinking":
            self.blink_duration += dt
            
            # Получаем длительность анимации
            face_part = self.face_parts_cache.get_part("eye", self.current_preset.parts["eye"][0])
            part_state = face_part.get_state("blink")
            
            from render.frame_description import AnimatedSpriteLayer
            if isinstance(part_state.layer, AnimatedSpriteLayer):
                # Считаем общую длительность анимации
                total_duration = sum(part_state.layer.frame_durations)
                
                # Если анимация завершилась, возвращаем предыдущее состояние
                if self.blink_duration >= total_duration:
                    self.current_states["eye"] = self.blink_prev_eye_state
                    self.blink_state = None
                    self.blink_prev_eye_state = None
                    self.time_to_next_blink = random.uniform(3, 5)
                    self.blink_elapsed_time = 0.0

    def update(self, dt: float, events: list[Event]):
        self._ensure_initialized()
        
        # Обновляем переходы частей лица
        self.transition_manager.update(dt)
        
        # Управляем морганием независимо от других обновлений
        if self.blink_enabled:
            # Если не моргаем, отсчитываем время до следующего моргания
            if self.blink_state is None:
                self.blink_elapsed_time += dt
                if self.blink_elapsed_time >= self.time_to_next_blink:
                    self._start_blink()
            else:
                # Если моргаем, обновляем длительность
                self._update_blink(dt)
        
        # Обновляем состояние рта на основе аудио
        if self.audio_enabled:
            mouth_state = self.audio_processor.update(dt)
            self.current_states["mouth"] = mouth_state
        
        # Разделяем события и запросы
        event_list = [e for e in events if isinstance(e, Event) and not isinstance(e, Query)]
        
        handle_events(self, dt, event_list)
    
    def handle_query(self, query: Query) -> QueryResult:
        """Обрабатывает запросы приложения"""
        return handle_queries(self, query)
        
    
    def render(self) -> FrameDescription:
        """Отрисовка лица на основе текущего пресета и состояний"""
        self._ensure_initialized()
        layers = []
        
        if self.current_preset:
            for part_type, (ref, _) in self.current_preset.parts.items():
                # Получаем часть лица
                face_part = self.face_parts_cache.get_part(part_type, ref)
                
                # Получаем текущее состояние
                state_name = self.current_states.get(part_type, face_part.default_state)
                part_state = face_part.get_state(state_name)
                
                # проверяем есть ли активный переход для этой части
                transition = self.transition_manager.get_transition(part_type)
                if transition and not transition.is_complete:
                    # используем смешанный слой из перехода
                    blended_layer = self.transition_manager.blend_layer(transition, part_state.layer)
                    layers.append(blended_layer)
                else:
                    # обычный слой
                    layers.append(part_state.layer)
        
        frame_desc = FrameDescription(layers=layers)
        return frame_desc