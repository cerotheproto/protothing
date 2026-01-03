
import importlib
from pathlib import Path
from apps.base import BaseApp
from api.app_commands import register_event_type
import logging
logger = logging.getLogger(__name__)
class AppManager:
    def __init__(self):
        self.active_app: BaseApp | None = None
        self.available_apps: dict[str, BaseApp] = {}
        self._pending_app: BaseApp | None = None  # приложение ожидающее перехода
        self._last_frame = None  # последний кадр для перехода
        self._load_apps()
        self._register_all_events()

    def _load_apps(self):
        """Автоматически загружает все приложения из папки apps"""
        apps_dir = Path(__file__).parent / "apps"
        
        if not apps_dir.exists():
            return
        
        # Проходим по всем подпапкам в apps
        for item in apps_dir.iterdir():
            if item.is_dir() and not item.name.startswith('_'):
                app_file = item / "app.py"
                if app_file.exists():
                    try:
                        # Формируем имя модуля: apps.folder_name.app
                        module_name = f"apps.{item.name}.app"
                        module = importlib.import_module(module_name)
                        
                        # Ищем класс, наследующий BaseApp
                        for attr_name in dir(module):
                            attr = getattr(module, attr_name)
                            if (isinstance(attr, type) and 
                                issubclass(attr, BaseApp) and 
                                attr is not BaseApp):
                                # Создаем экземпляр приложения
                                app_instance = attr()
                                self.available_apps[app_instance.name] = app_instance
                                logger.info(f"Application loaded: {app_instance.name}")
                                break
                    except Exception as e:
                        logger.error(f"Error loading application from {item.name}: {e}")

    def _register_all_events(self):
        """Автоматически регистрирует события всех приложений"""
        registered_events = set()
        
        for app in self.available_apps.values():
            for event_class in app.get_events():
                event_name = event_class.__name__
                if event_name not in registered_events:
                    register_event_type(event_class)
                    registered_events.add(event_name)
                    logger.debug(f"Event registered: {event_name}")

    def set_active_app(self, app: BaseApp, with_transition: bool = True):
        """Устанавливает активное приложение с опциональным переходом"""
        if self.active_app:
            self.active_app.stop()
        
        old_app = self.active_app
        self.active_app = app
        
        if self.active_app:
            self.active_app.start()
        
        # запускаем переход если нужно и есть предыдущий кадр
        if with_transition and old_app is not None and self._last_frame is not None:
            self._start_app_transition()

    
    def _start_app_transition(self):
        """Запускает переход между приложениями"""
        # импортируем здесь чтобы избежать циклических импортов
        from dependencies import transition_engine, renderer
        from render.frame_description import FrameDescription
        from render.frame import Frame
        
        if self._last_frame is None or self.active_app is None:
            return
        
        # получаем первый кадр нового приложения
        try:
            frame_desc = self.active_app.render()
            if isinstance(frame_desc, FrameDescription):
                new_frame = renderer.render_frame(frame_desc, 0.0)
            elif isinstance(frame_desc, Frame):
                new_frame = frame_desc
            else:
                return
            
            # запускаем переход
            transition_engine.start_transition(
                from_frame=self._last_frame,
                to_frame=new_frame
            )
        except Exception as e:
            logger.error(f"Error starting application transition: {e}")
    
    def save_last_frame(self, frame):
        """Сохраняет последний кадр для перехода"""
        from render.frame import Frame
        if isinstance(frame, Frame):
            self._last_frame = frame

    def set_active_app_by_name(self, app_name: str, with_transition: bool = True) -> bool:
        """Устанавливает активное приложение по имени"""
        if app_name in self.available_apps:
            self.set_active_app(self.available_apps[app_name], with_transition)
            return True
        return False

    def get_current_app(self) -> BaseApp | None:
        return self.active_app
    
    def get_available_apps(self) -> list[BaseApp]:
        return list(self.available_apps.values())
    
    def get_available_app_names(self) -> list[str]:
        """Возвращает список имен доступных приложений"""
        return list(self.available_apps.keys())