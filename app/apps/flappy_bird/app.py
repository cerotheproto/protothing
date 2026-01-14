import numpy as np
import logging
from apps.base import BaseApp
from models.app_contract import Event
from render.frame_description import FrameDescription, RectLayer, FillLayer, TextLayer
from apps.flappy_bird.events import Flap, ResetFlappyBirdGame

logger = logging.getLogger(__name__)


class FlappyBirdApp(BaseApp):
    name = "flappy_bird"
    
    def __init__(self):
        super().__init__()
        
        # Game field dimensions
        self.width = 64
        self.height = 32
        
        # Bird properties
        self.bird_x = 12
        self.bird_y = self.height // 2
        self.bird_size = 4
        self.bird_velocity = 0.0
        
        # Physics
        self.gravity = 50.0
        self.flap_strength = -18.0
        
        # Pipes
        self.pipe_width = 4
        self.pipe_gap = 10
        self.pipe_speed = 20.0
        self.pipes = []
        self.pipe_spawn_timer = 0.0
        self.pipe_spawn_interval = 2.0
        
        # Score
        self.score = 0
        self.game_over = False
    
    def start(self):
        super().start()
        self._reset_game()

    def stop(self):
        super().stop()
        self._reset_game()

    def _spawn_pipe(self):
        """Spawn new pipe pair"""
        gap_y = np.random.randint(self.pipe_gap // 2 + 2, self.height - self.pipe_gap // 2 - 2)
        self.pipes.append({
            'x': self.width,
            'gap_y': gap_y,
            'scored': False
        })
    
    def update(self, dt: float, events: list[Event]):
        # Handle events
        for event in events:
            if isinstance(event, Flap):
                if not self.game_over:
                    self.bird_velocity = self.flap_strength
            elif isinstance(event, ResetFlappyBirdGame):
                self._reset_game()
        
        if self.game_over:
            return
        
        # Update bird physics
        self.bird_velocity += self.gravity * dt
        self.bird_y += self.bird_velocity * dt
        
        # Check ground and ceiling collision
        if self.bird_y < 0 or self.bird_y + self.bird_size > self.height:
            self.game_over = True
            return
        
        # Update pipes
        for pipe in self.pipes:
            pipe['x'] -= self.pipe_speed * dt
            
            # Check if bird passed pipe
            if not pipe['scored'] and pipe['x'] + self.pipe_width < self.bird_x:
                pipe['scored'] = True
                self.score += 1
            
            # Check collision with pipe
            if (self.bird_x + self.bird_size > pipe['x'] and 
                self.bird_x < pipe['x'] + self.pipe_width):
                # Check if bird is not in gap
                if (self.bird_y < pipe['gap_y'] - self.pipe_gap // 2 or
                    self.bird_y + self.bird_size > pipe['gap_y'] + self.pipe_gap // 2):
                    self.game_over = True
                    return
        
        # Remove off-screen pipes
        self.pipes = [p for p in self.pipes if p['x'] + self.pipe_width > 0]
        
        # Spawn new pipes
        self.pipe_spawn_timer += dt
        if self.pipe_spawn_timer >= self.pipe_spawn_interval:
            self.pipe_spawn_timer = 0.0
            self._spawn_pipe()
    
    def _reset_game(self):
        """Reset game state"""
        self.bird_y = self.height // 2
        self.bird_velocity = 0.0
        self.pipes = []
        self.pipe_spawn_timer = 0.0
        self.score = 0
        self.game_over = False
    
    def render(self):
        layers = []
        
        # Background
        layers.append(FillLayer(color=(135, 206, 235, 255)))
        
        # Pipes
        for pipe in self.pipes:
            # Top pipe
            layers.append(RectLayer(
                x=int(pipe['x']),
                y=0,
                width=self.pipe_width,
                height=int(pipe['gap_y'] - self.pipe_gap // 2),
                color=(34, 139, 34, 255)
            ))
            
            # Bottom pipe
            layers.append(RectLayer(
                x=int(pipe['x']),
                y=int(pipe['gap_y'] + self.pipe_gap // 2),
                width=self.pipe_width,
                height=int(self.height - (pipe['gap_y'] + self.pipe_gap // 2)),
                color=(34, 139, 34, 255)
            ))
        
        # Bird
        layers.append(RectLayer(
            x=int(self.bird_x),
            y=int(self.bird_y),
            width=self.bird_size,
            height=self.bird_size,
            color=(255, 255, 0, 255)
        ))
        
        # Score
        layers.append(TextLayer(
            text=f"{self.score}",
            x=2,
            y=2,
            font_size=6,
            color=(255, 255, 255, 255)
        ))
        
        # Game over text
        if self.game_over:
            layers.append(TextLayer(
                text="GAME OVER",
                x=self.width // 2 - 25,
                y=self.height // 2 - 3,
                font_size=6,
                color=(255, 0, 0, 255)
            ))
        
        return FrameDescription(
            width=self.width,
            height=self.height,
            layers=layers
        )
    
    def get_events(self):
        return [Flap, ResetFlappyBirdGame]
