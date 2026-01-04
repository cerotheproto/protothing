from typing import TYPE_CHECKING
from models.app_contract import Event, Query, QueryResult
import logging

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from apps.video_player.app import VideoPlayerApp


class PlayVideo(Event):
    """Start playing a video from the list"""
    video_name: str


class PauseVideo(Event):
    """Pause current video playback"""
    pass


class ResumeVideo(Event):
    """Resume video playback"""
    pass


class RestartVideo(Event):
    """Restart current video from the beginning"""
    pass


class GetVideoState(Query):
    """Get current video player state"""
    pass


class VideoStateResult(QueryResult):
    """Result of GetVideoState query"""
    available_videos: list[str]
    current_video: str | None
    is_playing: bool


def handle_events(self: "VideoPlayerApp", dt: float, events: list[Event]):
    """Handle video player events"""
    for event in events:
        if isinstance(event, PlayVideo):
            logger.info(f"PlayVideo event: {event.video_name}")
            if self._open_video(event.video_name):
                self.is_playing = True
            
        elif isinstance(event, PauseVideo):
            logger.info("PauseVideo event")
            self.is_playing = False
            self.time_accumulator = 0.0
            
        elif isinstance(event, ResumeVideo):
            logger.info("ResumeVideo event")
            if self.cap is not None:
                self.is_playing = True
                self.time_accumulator = 0.0
            
        elif isinstance(event, RestartVideo):
            logger.info("RestartVideo event")
            if self.cap is not None:
                self.cap.set(0, 0)  # cv2.CAP_PROP_POS_FRAMES
                self.is_playing = True
                self.time_accumulator = 0.0


def handle_queries(self: "VideoPlayerApp", query: Query) -> QueryResult:
    """Handle video player queries"""
    if isinstance(query, GetVideoState):
        return VideoStateResult(
            available_videos=self._get_videos_list(),
            current_video=self.current_video,
            is_playing=self.is_playing
        )
    
    raise NotImplementedError(f"Query {type(query).__name__} is not supported")


def get_events(self: "VideoPlayerApp") -> list[type[Event]]:
    """Return list of supported events"""
    return [PlayVideo, PauseVideo, ResumeVideo, RestartVideo]


def get_queries(self: "VideoPlayerApp") -> list[type[Query]]:
    """Return list of supported queries"""
    return [GetVideoState]
