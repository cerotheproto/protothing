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
        self.playback_fps = 30.0
        self.frame_interval = 1 / self.video_fps
        self.time_accumulator = 0.0
        self.frame_step = 1
        self.max_frame_batch = 3
        self.last_frame: Frame | None = None
        self.videos_dir = Path("assets/videos")
        self._initialized = False
        self.resize_interpolation = cv2.INTER_LINEAR
        self.target_output_fps = 30.0
        
    def _ensure_initialized(self):
        """Lazy initialization with loaded config"""
        if self._initialized:
            return
        
        import dependencies
        cfg = dependencies.config.get().video_player
        self.target_output_fps = min(cfg.max_fps, 60)
        default_video = cfg.default_video
        if default_video:
            self._open_video(default_video)
        
        self._initialized = True
    
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
        
        self._configure_capture()
        
        self.current_video = video_name
        self.is_playing = True
        self._update_video_timing()
        logger.info(f"Opened video: {video_name}")
        return True
        
    def start(self):
        super().start()
        self._ensure_initialized()
        logger.info("Video player started")
        
    def stop(self):
        super().stop()
        if self.cap:
            self.cap.release()
            self.cap = None
        self.is_playing = False
        self.current_video = None
        self._initialized = False
        logger.info("Video player stopped")
        
    def update(self, dt: float, events: list[Event]):
        handle_events(self, dt, events)
        if not self.is_playing or not self.cap:
            return

        self.time_accumulator += dt
        max_accumulator = self.frame_interval * self.max_frame_batch
        if self.time_accumulator > max_accumulator:
            self.time_accumulator = max_accumulator

        if self.time_accumulator < self.frame_interval:
            return

        frames_due = max(1, int(self.time_accumulator / self.frame_interval))
        frames_due = min(frames_due, self.max_frame_batch)
        self.time_accumulator -= frames_due * self.frame_interval

        if not self._read_and_process_frame(frames_due):
            self.is_playing = False
    
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
        self.playback_fps = min(self.video_fps, self.target_output_fps)
        self.frame_interval = 1 / self.playback_fps
        self.time_accumulator = 0.0
        self.frame_step = max(1, int(round(self.video_fps / self.playback_fps)))

    def _read_and_process_frame(self, frames_due: int = 1) -> bool:
        if not self.cap:
            return False

        frames_to_skip = max(0, frames_due * self.frame_step - 1)
        if frames_to_skip and not self._skip_frames(frames_to_skip):
            return False

        ret, frame = self.cap.read()
        if not ret:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
            if not ret:
                return False

        self.last_frame = self._create_frame(frame)
        return True

    def _skip_frames(self, count: int) -> bool:
        if not self.cap:
            return False

        for _ in range(count):
            if self.cap.grab():
                continue
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            if not self.cap.grab():
                return False
        return True

    def _configure_capture(self):
        if not self.cap:
            return
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)

    def _create_frame(self, frame: np.ndarray) -> Frame:
        height, width = frame.shape[:2]
        scale_width = self.frame_width / width
        scale_height = self.frame_height / height
        scale = min(scale_width, scale_height)

        new_width = max(1, int(width * scale))
        new_height = max(1, int(height * scale))

        resized = cv2.resize(frame, (new_width, new_height), interpolation=self.resize_interpolation)
        frame_rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        result_frame = Frame(self.frame_width, self.frame_height)
        result_frame.pixels = np.zeros((self.frame_height, self.frame_width, 3), dtype=np.uint8)

        y_offset = (self.frame_height - new_height) // 2
        x_offset = (self.frame_width - new_width) // 2
        result_frame.pixels[y_offset:y_offset + new_height, x_offset:x_offset + new_width] = frame_rgb
        return result_frame
