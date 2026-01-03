"""
sorry for comments in russian, i had no plans to share this code publicly
they are just for my own understanding
maybe i'll translate them later and document all properly
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from api.apps import app_router as apps_router
from api.config import config_router as config_router
from api.app_commands import generate_app_router, event_queue, create_events_router
from api.effects import router as effects_router
from api.display import router as display_router
from api.files import router as files_router
from api.brightness import router as brightness_router
from dependencies import app_manager, config, driver, renderer, effect_manager, display_manager, transition_engine
from render.frame_description import FrameDescription
from render.frame import Frame
from render.led_strip import generate_led_strip_pixels, find_rainbow_effect
from time import time
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import logging
import os


logger = logging.getLogger(__name__)


async def main_loop_task():
    """Главный цикл обновления и отрисовки приложений"""
    last = time()
    cfg = config.get()
    frame_time = 1.0 / cfg.system.target_fps  # время на один кадр
    led_count = cfg.led_strip.led_number

    while True:
        try:
            now = time()
            delta = now - last
            last = now

            # собираем события из очереди
            events = []
            while not event_queue.empty():
                try:
                    events.append(event_queue.get_nowait())
                except asyncio.QueueEmpty:
                    break

            app = app_manager.get_current_app()
            if app is None:
                await asyncio.sleep(0.01)
                continue
            
            app.update(delta, events) # обновляем состояние приложения
            frame_desc = app.render() # получаем описание кадра или сам кадр
            
            # для LED ленты нужен rainbow effect если есть
            rainbow_effect = None
            
            if isinstance(frame_desc, FrameDescription):
                frame_desc.effects.extend(effect_manager.get_effects())  # добавляем эффекты из менеджера
                effect_manager.update_layers_cache(frame_desc.layers)  # обновляем кеш слоев для cleanup
                rainbow_effect = find_rainbow_effect(frame_desc.effects)
                frame = renderer.render_frame(frame_desc, delta) # если описание, то рендерим с dt
            elif isinstance(frame_desc, Frame):
                frame = frame_desc  # если уже кадр, то просто берем его
            else:
                continue  # пропускаем итерацию, если нет кадра

            # применяем переход между кадрами если есть
            frame = transition_engine.process(frame, delta)

            # сохраняем кадр для возможного перехода при смене приложения
            app_manager.save_last_frame(frame)

            frame = display_manager.process_frame(frame)
            await driver.display_frame(frame)
            
            # формируем и отправляем кадр для LED ленты 
            led_pixels = generate_led_strip_pixels(led_count, frame, rainbow_effect)
            await driver.send_led_strip_frame(led_pixels)

            # ограничиваем FPS в соответствии с конфигом
            elapsed = time() - now
            sleep_time = frame_time - elapsed
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            else:
                # даже если не успеваем - даём другим задачам шанс выполниться
                await asyncio.sleep(0)
    
        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
            await asyncio.sleep(0.01)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # инициализация при старте
    cfg = config.get()
    driver.init_from_config(cfg.system.transport, ws_enabled=cfg.system.ws_enabled)
    await driver.start()
    
    # ХАРДКОД: обработчик нажатия кнопки
    # Здесь указывается какой ивент будет вызываться при нажатии кнопки
    def handle_button_press(button_id: int):
        logger.info(f"Processing button press {button_id}")
        # TODO: сделать нормальный выбор ивента через конфиг
        # Сейчас хардкодим вызов JumpEvent для dino_game
        from apps.dino_game.events import JumpEvent
        event_queue.put_nowait(JumpEvent())
    
    # Устанавливаем коллбек для UDP транспорта
    if hasattr(driver.transport, 'set_button_callback'):
        driver.transport.set_button_callback(handle_button_press)
    
    # устанавливаем стартовое приложение
    if cfg.system.startup_app:
        app_manager.set_active_app_by_name(cfg.system.startup_app)
    
    # регистрируем WS эндпоинт на /ws если WS включен в конфиге
    ws_transport = driver.get_ws_transport()
    if ws_transport is not None:
        async def websocket_endpoint(websocket: WebSocket):
            await ws_transport.handle_connection(websocket)
        
        app.add_websocket_route("/ws", websocket_endpoint)
    
    # запускаем главный цикл как фоновую задачу
    loop_task = asyncio.create_task(main_loop_task())
    
    yield
    
    # остановка при завершении
    loop_task.cancel()
    try:
        await loop_task
    except asyncio.CancelledError:
        pass
    
    await driver.stop()


app = FastAPI(lifespan=lifespan)

app.include_router(apps_router, prefix="/apps", tags=["apps"])
app.include_router(config_router, prefix="/config", tags=["config"])
app.include_router(effects_router, prefix="/effects", tags=["effects"])
app.include_router(display_router, prefix="/display", tags=["display"])
app.include_router(files_router, prefix="/files", tags=["files"])
app.include_router(create_events_router(), prefix="/events", tags=["events"])
app.include_router(brightness_router, prefix="/brightness", tags=["brightness"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# регистрируем роутеры приложений на основе их контрактов
for app_instance in app_manager.get_available_apps():
    router = generate_app_router(app_instance)
    app.include_router(router, prefix=f"/apps/{app_instance.name}", tags=[app_instance.name])

if __name__ == "__main__":
    import uvicorn
    
    os.makedirs("logs", exist_ok=True)
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_config="log_conf.yaml")