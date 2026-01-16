"""
sorry for comments in russian, i had no plans to share this code publicly
they are just for my own understanding
maybe i'll translate them later and document everthing properly (if i ever get to it)
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from httpx import AsyncClient
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
import random
import subprocess
import numpy as np

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

            # пытаемся применить ожидающее приложение если эффекты очистились
            app_manager._apply_pending_app()

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
            elif isinstance(frame_desc, tuple) and len(frame_desc) == 2:
                # tuple of two different frames for left and right 64x32 displays
                left_frame_desc, right_frame_desc = frame_desc
                
                left_frame = None
                right_frame = None
                
                # render left frame
                if isinstance(left_frame_desc, FrameDescription):
                    left_frame_desc.effects.extend(effect_manager.get_effects())
                    effect_manager.update_layers_cache(left_frame_desc.layers)
                    rainbow_effect = find_rainbow_effect(left_frame_desc.effects)
                    left_frame = renderer.render_frame(left_frame_desc, delta)
                elif isinstance(left_frame_desc, Frame):
                    left_frame = left_frame_desc
                
                # render right frame
                if isinstance(right_frame_desc, FrameDescription):
                    right_frame_desc.effects.extend(effect_manager.get_effects())
                    effect_manager.update_layers_cache(right_frame_desc.layers)
                    right_frame = renderer.render_frame(right_frame_desc, delta)
                elif isinstance(right_frame_desc, Frame):
                    right_frame = right_frame_desc
                
                # combine both 64x32 frames into single 128x32 frame
                if left_frame is not None and right_frame is not None:
                    frame = Frame(128, 32)
                    frame.pixels = np.concatenate([left_frame.pixels, right_frame.pixels], axis=1)
                else:
                    await asyncio.sleep(0.01)
                    continue
            else:
                await asyncio.sleep(0.01)
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

    saved_effect_params = None
    webui_process = None

    def handle_button_press(button_id: int):
        nonlocal saved_effect_params
        logger.info(f"Processing button press {button_id}")                    
        match app_manager.get_current_app().name:
            case "reactive_face":
                if random.random() < 0.15: # 15% шанс тролинга
                #if True: # для теста
                    if random.random() < 0.5: 
                        saved_effect_params = effect_manager.save_effect_params()
                        app_manager.set_active_app_by_name("video_player")
                        async def switch_back():
                            await asyncio.sleep(5)    
                            app_manager.set_active_app_by_name("reactive_face")
                            await asyncio.sleep(1)  # даём время на переключение
                            effect_manager.restore_effects(saved_effect_params)
                    else:
                        saved_effect_params = effect_manager.save_effect_params()
                        app_manager.set_active_app_by_name("bsod")
                    asyncio.create_task(switch_back())

                else:
                    logger.info("Sending Boop event")
                    from apps.reactive_face.events import Boop
                    event = Boop()
                    event_queue.put_nowait(event)
            case "bsod":
                app_manager.set_active_app_by_name("reactive_face")
                async def switch_back_effects():
                    await asyncio.sleep(1)  # даём время на переключение
                    effect_manager.restore_effects(saved_effect_params)
                asyncio.create_task(switch_back_effects())

                
    
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
        
        app.add_websocket_route("/api/ws", websocket_endpoint)
    
    # запускаем главный цикл как фоновую задачу
    loop_task = asyncio.create_task(main_loop_task())
    
    # запускаем WebUI если включен в конфиге
    if cfg.webui.enabled:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        webui_path = os.path.normpath(os.path.join(project_root, cfg.webui.path))
        if os.path.exists(webui_path):
            logger.info(f"Starting WebUI from {webui_path} with command: {cfg.webui.run_cmd}")
            try:
                os.makedirs("logs", exist_ok=True)
                webui_log_path = os.path.join(os.path.dirname(__file__), "logs", "webui.log")
                with open(webui_log_path, "a") as log_file:
                    webui_process = subprocess.Popen(
                        cfg.webui.run_cmd,
                        shell=True,
                        cwd=webui_path,
                        stdout=log_file,
                        stderr=log_file
                    )
                    # даём времени на загрузку
                    await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"Failed to start WebUI: {e}")
        else:
            logger.warning(f"WebUI path not found: {webui_path}")
    
    yield
    
    # остановка при завершении
    loop_task.cancel()
    try:
        await loop_task
    except asyncio.CancelledError:
        pass
    
    if webui_process:
        logger.info("Stopping WebUI process")
        webui_process.terminate()
        try:
            webui_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            webui_process.kill()
    
    await driver.stop()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(apps_router, prefix="/api/apps", tags=["apps"])
app.include_router(config_router, prefix="/api/config", tags=["config"])
app.include_router(effects_router, prefix="/api/effects", tags=["effects"])
app.include_router(display_router, prefix="/api/display", tags=["display"])
app.include_router(files_router, prefix="/api/files", tags=["files"])
app.include_router(create_events_router(), prefix="/api/events", tags=["events"])
app.include_router(brightness_router, prefix="/api/brightness", tags=["brightness"])

# регистрируем роутеры приложений на основе их контрактов
for app_instance in app_manager.get_available_apps():
    router = generate_app_router(app_instance)
    app.include_router(router, prefix=f"/api/apps/{app_instance.name}", tags=[app_instance.name])

# настраиваем reverse proxy для WebUI если включен (должен быть в конце для совпадения всех остальных маршрутов)
cfg = config.get()
if cfg.webui.enabled:
    from fastapi.responses import StreamingResponse
    
    @app.get("/{path_name:path}")
    async def webui_proxy_get(path_name: str):
        try:
            async with AsyncClient() as client:
                url = f"http://localhost:{cfg.webui.port}/{path_name}"
                response = await client.get(url, follow_redirects=True)
                
                headers = dict(response.headers)
                headers.pop("content-encoding", None)
                
                return StreamingResponse(
                    iter([response.content]),
                    status_code=response.status_code,
                    headers=headers
                )
        except Exception as e:
            logger.warning(f"WebUI proxy error for {path_name}: {e}")
            return None

if __name__ == "__main__":
    import uvicorn
    
    os.makedirs("logs", exist_ok=True)
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_config="log_conf.yaml")
