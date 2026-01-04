"""Frame buffer pool for efficient memory reuse"""

from render.frame import Frame
from collections import deque


class FramePool:
    """Pool of preallocated Frame objects to avoid repeated allocation"""
    
    def __init__(self, width: int, height: int, pool_size: int = 4):
        self.width = width
        self.height = height
        self.pool_size = pool_size
        self._available = deque(maxlen=pool_size)
        self._in_use = set()
        
        # preallocate frames
        for _ in range(pool_size):
            frame = Frame(width, height)
            self._available.append(frame)
    
    def acquire(self) -> Frame:
        """Get a frame from the pool"""
        if self._available:
            frame = self._available.popleft()
        else:
            # pool exhausted, create new frame
            frame = Frame(self.width, self.height)
        
        self._in_use.add(id(frame))
        # clear pixels for reuse
        frame.pixels.fill(0)
        return frame
    
    def release(self, frame: Frame) -> None:
        """Return a frame to the pool"""
        frame_id = id(frame)
        if frame_id in self._in_use:
            self._in_use.remove(frame_id)
            if len(self._available) < self.pool_size:
                self._available.append(frame)
    
    def clear(self) -> None:
        """Clear the pool and release all frames"""
        self._available.clear()
        self._in_use.clear()
        
        # recreate pool
        for _ in range(self.pool_size):
            frame = Frame(self.width, self.height)
            self._available.append(frame)


# Global frame pools for common sizes
_frame_pools = {}


def get_frame_pool(width: int, height: int, pool_size: int = 4) -> FramePool:
    """Get or create a frame pool for given dimensions"""
    key = (width, height)
    if key not in _frame_pools:
        _frame_pools[key] = FramePool(width, height, pool_size)
    return _frame_pools[key]


def acquire_frame(width: int, height: int) -> Frame:
    """Acquire a frame from the appropriate pool"""
    pool = get_frame_pool(width, height)
    return pool.acquire()


def release_frame(frame: Frame) -> None:
    """Release a frame back to its pool"""
    key = (frame.width, frame.height)
    if key in _frame_pools:
        _frame_pools[key].release(frame)
