import subprocess
import mss
import numpy as np
import re
from PIL import Image
from apps.base import BaseApp
from apps.x11_display.models import Launch, Close, UpdateGeometry, Status, StatusResult, RefreshWindow
from render.frame import Frame
from render.frame_description import FrameDescription
from typing import Optional
import time
import os

class X11DisplayApp(BaseApp):
    name = "x11_display"

    def __init__(self):
        super().__init__()
        self.process: Optional[subprocess.Popen] = None
        self.command: Optional[str] = None
        self.geometry = {"top": 0, "left": 0, "width": 64, "height": 32}
        self.sct = mss.mss()
        self.target_width = 64
        self.target_height = 32
        self.display_env = os.environ.get("DISPLAY", ":0")
        self.window_id: Optional[str] = None
        self.search_attempts = 0
        self.max_search_attempts = 50  # примерно 2.5 сек при dt=0.05
        self.active_crop: Optional[tuple[int, int, int, int]] = None  # кешированная область активного контента

    def start(self):
        super().start()

    def stop(self):
        super().stop()
        self._stop_process()

    def _stop_process(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
            self.command = None
            self.window_id = None
            self.search_attempts = 0
            self.active_crop = None

    def _get_window_coords(self, window_id: str) -> Optional[dict]:
        """Получить координаты окна (x, y, w, h) без декораций"""
        try:
            env = os.environ.copy()
            env["DISPLAY"] = self.display_env
            
            result = subprocess.run(
                ["xdotool", "getwindowgeometry", "--shell", window_id],
                env=env,
                capture_output=True,
                timeout=2
            )
            geom_output = result.stdout.decode()
            
            x_match = re.search(r'^X=(\d+)', geom_output, re.MULTILINE)
            y_match = re.search(r'^Y=(\d+)', geom_output, re.MULTILINE)
            w_match = re.search(r'^WIDTH=(\d+)', geom_output, re.MULTILINE)
            h_match = re.search(r'^HEIGHT=(\d+)', geom_output, re.MULTILINE)
            
            if x_match and y_match and w_match and h_match:
                x = int(x_match.group(1))
                y = int(y_match.group(1))
                w = int(w_match.group(1))
                h = int(h_match.group(1))
                
                # Получить границы окна
                result = subprocess.run(
                    ["xprop", "-id", window_id, "_NET_FRAME_EXTENTS"],
                    env=env,
                    capture_output=True,
                    timeout=2
                )
                extents_output = result.stdout.decode()
                extents_match = re.search(r'=\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)', extents_output)
                
                if extents_match:
                    left_border = int(extents_match.group(1))
                    right_border = int(extents_match.group(2))
                    top_border = int(extents_match.group(3))
                    bottom_border = int(extents_match.group(4))
                    x += left_border
                    y += top_border
                    w -= (left_border + right_border)
                    h -= (top_border + bottom_border)
                
                return {"top": y, "left": x, "width": w, "height": h}
        except Exception:
            pass
        return None

    def _find_window_for_process(self) -> Optional[str]:
        """Поиск окна для процесса по имени команды"""
        if not self.process or not self.command:
            return None
        
        try:
            env = os.environ.copy()
            env["DISPLAY"] = self.display_env
            
            # Поиск окон по классу (обычно совпадает с названием программы)
            result = subprocess.run(
                ["xdotool", "search", "--class", ".*"],
                env=env,
                capture_output=True,
                timeout=2
            )
            window_ids = result.stdout.decode().strip().split('\n')
            
            for wid in window_ids:
                if not wid:
                    continue
                
                coords = self._get_window_coords(wid)
                if coords and coords["width"] > 0 and coords["height"] > 0:
                    # Пропускаем очень маленькие окна (вероятно декорации/панели)
                    if coords["width"] >= 100 and coords["height"] >= 100:
                        return wid
        except Exception:
            pass
        
        return None

    def update(self, dt: float, events: list):
        for event in events:
            if isinstance(event, Launch):
                self._stop_process()
                self.command = event.command
                cmd = [event.command] + event.args
                try:
                    self.process = subprocess.Popen(cmd)
                    print(f"Launched {self.command} with PID {self.process.pid}")
                except Exception as e:
                    print(f"Failed to launch {self.command}: {e}")
            
            elif isinstance(event, Close):
                self._stop_process()
            
            elif isinstance(event, UpdateGeometry):
                self.geometry = {
                    "top": event.y,
                    "left": event.x,
                    "width": event.width,
                    "height": event.height
                }
                self.active_crop = None  # сбросить кеш
            
            elif isinstance(event, RefreshWindow):
                if self.window_id:
                    coords = self._get_window_coords(self.window_id)
                    if coords:
                        self.geometry = coords
                        self.active_crop = None  # сбросить кеш при обновлении геометрии

        # Поиск окна запущенного приложения
        if self.process and not self.window_id and self.search_attempts < self.max_search_attempts:
            self.search_attempts += 1
            self.window_id = self._find_window_for_process()
            if self.window_id:
                print(f"Found window: {self.window_id}")
                coords = self._get_window_coords(self.window_id)
                if coords:
                    self.geometry = coords
                    self.active_crop = None

    def _detect_active_area(self, img: Image.Image) -> Optional[tuple[int, int, int, int]]:
        """Находит активную область изображения один раз"""
        arr = np.array(img)
        mask = np.any(arr > 10, axis=2)
        if mask.any():
            ys, xs = np.nonzero(mask)
            top = max(int(ys.min()) - 2, 0)
            bottom = min(int(ys.max()) + 3, arr.shape[0])
            left = max(int(xs.min()) - 2, 0)
            right = min(int(xs.max()) + 3, arr.shape[1])
            return (left, top, right, bottom)
        return None

    def render(self) -> Optional[FrameDescription | Frame]:
        try:
            if self.geometry["width"] <= 0 or self.geometry["height"] <= 0:
                return Frame(self.target_width, self.target_height)

            sct_img = self.sct.grab(self.geometry)
            
            # Быстрое преобразование через numpy без промежуточного PIL
            arr = np.frombuffer(sct_img.bgra, dtype=np.uint8).reshape(sct_img.height, sct_img.width, 4)
            arr = arr[:, :, :3][:, :, ::-1]  # BGRA -> RGB

            # Определяем активную область только один раз
            if self.active_crop is None:
                mask = np.any(arr > 10, axis=2)
                if mask.any():
                    ys, xs = np.nonzero(mask)
                    top = max(int(ys.min()) - 2, 0)
                    bottom = min(int(ys.max()) + 3, arr.shape[0])
                    left = max(int(xs.min()) - 2, 0)
                    right = min(int(xs.max()) + 3, arr.shape[1])
                    self.active_crop = (left, top, right, bottom)
            
            # Применяем кешированный кроп
            if self.active_crop:
                left, top, right, bottom = self.active_crop
                arr = arr[top:bottom, left:right]

            src_h, src_w = arr.shape[:2]
            if src_w <= 0 or src_h <= 0:
                return Frame(self.target_width, self.target_height)

            # Letterbox/pillarbox - вписываем с черными рамками
            target_ratio = self.target_width / self.target_height
            src_ratio = src_w / src_h

            if src_ratio > target_ratio:
                # Исходник шире - pillarbox (рамки сверху/снизу)
                new_w = self.target_width
                new_h = int(self.target_width / src_ratio)
            else:
                # Исходник выше - letterbox (рамки по бокам)
                new_h = self.target_height
                new_w = int(self.target_height * src_ratio)

            img = Image.fromarray(arr)
            img = img.resize((new_w, new_h), Image.Resampling.NEAREST)
            
            # Создаем черный кадр и вставляем изображение по центру
            frame = Frame(self.target_width, self.target_height)
            resized = np.array(img)
            
            offset_x = (self.target_width - new_w) // 2
            offset_y = (self.target_height - new_h) // 2
            frame.pixels[offset_y:offset_y + new_h, offset_x:offset_x + new_w] = resized
            
            return frame
        except Exception:
            return Frame(self.target_width, self.target_height)

    def get_queries(self):
        return [Status]

    def get_events(self):
        return [Launch, Close, UpdateGeometry, RefreshWindow]

    def handle_query(self, query):
        if isinstance(query, Status):
            return StatusResult(
                running=self.process is not None and self.process.poll() is None,
                command=self.command,
                geometry=self.geometry
            )
        return super().handle_query(query)
