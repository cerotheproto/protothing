import cv2
import numpy as np
import os
from pathlib import Path
from apps.base import BaseApp
from render.frame import Frame
from models.app_contract import Event
from .events import handle_events, get_events as imported_get_events, get_queries as imported_get_queries, handle_queries
from render.layers.text import TextLayer
from render.frame_description import FrameDescription
import logging

logger = logging.getLogger(__name__)


class VideoPlayerApp(BaseApp):
    name = "video_player"
    
    def __init__(self):
        super().__init__()

        self.cap = None
        self.is_playing = False
        self.current_video: str | None = None
        self.frame_width = 64
        self.frame_height = 32
        self.video_fps = 60.0
        self.frame_interval = 1 / self.video_fps
        self.time_accumulator = 0.0
        self.last_frame: Frame | None = None
        self.videos_dir = Path("assets/videos")
        
    def _get_videos_list(self) -> list[str]:
        """Get list of video files from assets/videos directory"""
        if not self.videos_dir.exists():
            return []
        
        video_extensions = ('.mp4', '.avi', '.mov', '.mkv', '.webm')
        videos = [f.name for f in self.videos_dir.iterdir() if f.suffix.lower() in video_extensions]
        return sorted(videos)
    
    def _open_video(self, video_name: str) -> bool:
        """Open video file and prepare for playback"""
        video_path = self.videos_dir / video_name
        
        if not video_path.exists():
            logger.error(f"Video file not found: {video_path}")
            return False
        
        if self.cap is not None:
            self.cap.release()
        
        self.cap = cv2.VideoCapture(str(video_path))
        if not self.cap.isOpened():
            logger.error(f"Failed to open video: {video_path}")
            return False
        
        self.current_video = video_name
        self.is_playing = True
        self._update_video_timing()
        logger.info(f"Opened video: {video_name}")
        return True
        
    def start(self):
        super().start()
        logger.info("Video player started")
        
    def stop(self):
        super().stop()
        if self.cap:
            self.cap.release()
            self.cap = None
        self.is_playing = False
        self.current_video = None
        logger.info("Video player stopped")
        
    def update(self, dt: float, events: list[Event]):
        handle_events(self, dt, events)
        if not self.is_playing or not self.cap:
            return

        self.time_accumulator += dt
        while self.time_accumulator >= self.frame_interval:
            if not self._read_and_process_frame():
                break
            self.time_accumulator -= self.frame_interval
    
    def handle_query(self, query):
        return handle_queries(self, query)
        
    def get_events(self):
        return imported_get_events(self)
    
    def get_queries(self):
        return imported_get_queries(self)
    
    def render(self) -> Frame | FrameDescription| None:
        if self.current_video is None:
            return FrameDescription(layers=[TextLayer(x=5, y=2, text="No video\nloaded", font_size=6)])
        if not self.last_frame:
            return None
        
        return self.last_frame

    def _update_video_timing(self):
        if not self.cap:
            return
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        validated_fps = fps if fps and fps >= 1.0 else 60.0
        self.video_fps = validated_fps
        self.frame_interval = 1 / self.video_fps
        self.time_accumulator = 0.0

    def _read_and_process_frame(self) -> bool:
        if not self.cap:
            return False

        ret, frame = self.cap.read()
        if not ret:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
            if not ret:
                return False

        self.last_frame = self._create_frame(frame)
        return True

    def _create_frame(self, frame: np.ndarray) -> Frame:
        height, width = frame.shape[:2]
        scale_width = self.frame_width / width
        scale_height = self.frame_height / height
        scale = min(scale_width, scale_height)

        new_width = max(1, int(width * scale))
        new_height = max(1, int(height * scale))

        resized = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)
        frame_rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        result_frame = Frame(self.frame_width, self.frame_height)
        result_frame.pixels = np.zeros((self.frame_height, self.frame_width, 3), dtype=np.uint8)

        y_offset = (self.frame_height - new_height) // 2
        x_offset = (self.frame_width - new_width) // 2
        result_frame.pixels[y_offset:y_offset + new_height, x_offset:x_offset + new_width] = frame_rgb
        return result_frame
