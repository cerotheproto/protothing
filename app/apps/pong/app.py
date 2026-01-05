import numpy as np
import logging
from apps.base import BaseApp
from models.app_contract import Event
from render.frame_description import FrameDescription, RectLayer, FillLayer, TextLayer
from apps.pong.events import MovePlayer, ResetGame

logger = logging.getLogger(__name__)


class PongApp(BaseApp):
    name = "pong"
    
    def __init__(self):
        super().__init__()
        
        # Game field dimensions
        self.width = 64
        self.height = 32
        
        # Paddle dimensions
        self.paddle_width = 2
        self.paddle_height = 8
        
        # Paddle positions (y-coordinates, x is fixed)
        self.player1_y = self.height // 2 - self.paddle_height // 2
        self.player2_y = self.height // 2 - self.paddle_height // 2
        
        # Paddle speed
        self.paddle_speed = 15.0  # pixels per second
        
        # Ball state
        self.ball_x = self.width // 2
        self.ball_y = self.height // 2
        self.ball_size = 2
        self.ball_velocity_x = 20.0
        self.ball_velocity_y = 15.0
        
        # Score
        self.score_player1 = 0
        self.score_player2 = 0
        
        # Player movement
        self.player1_direction = 0  # -1 up, 1 down, 0 stop
        self.player2_direction = 0
    
    def start(self):
        super().start()
        self._reset_ball()
    
    def _reset_ball(self):
        """Reset ball to center with random direction"""
        self.ball_x = self.width // 2
        self.ball_y = self.height // 2
        
        # Random direction
        direction = np.random.choice([-1, 1])
        self.ball_velocity_x = 20.0 * direction
        self.ball_velocity_y = np.random.uniform(-15.0, 15.0)
    
    def update(self, dt: float, events: list[Event]):
        # Handle events
        for event in events:
            logger.info(f"Pong received event: {type(event).__name__} - {event}")
            if isinstance(event, MovePlayer):
                logger.info(f"Player {event.player_id} direction: {event.direction}")
                if event.player_id == 1:
                    self.player1_direction = event.direction
                elif event.player_id == 2:
                    self.player2_direction = event.direction
            elif isinstance(event, ResetGame):
                self.score_player1 = 0
                self.score_player2 = 0
                self._reset_ball()
        
        # Update paddle positions
        if self.player1_direction != 0:
            new_y = self.player1_y + self.player1_direction * self.paddle_speed * dt
            self.player1_y = np.clip(new_y, 0, self.height - self.paddle_height)
        
        if self.player2_direction != 0:
            new_y = self.player2_y + self.player2_direction * self.paddle_speed * dt
            self.player2_y = np.clip(new_y, 0, self.height - self.paddle_height)
        
        # Update ball position
        self.ball_x += self.ball_velocity_x * dt
        self.ball_y += self.ball_velocity_y * dt
        
        # Ball collision with top/bottom walls
        if self.ball_y <= 0 or self.ball_y >= self.height - self.ball_size:
            self.ball_velocity_y *= -1
            self.ball_y = np.clip(self.ball_y, 0, self.height - self.ball_size)
        
        # Ball collision with paddles
        # Player 1 paddle (left)
        if (self.ball_x <= self.paddle_width and 
            self.player1_y <= self.ball_y <= self.player1_y + self.paddle_height):
            self.ball_velocity_x = abs(self.ball_velocity_x)
            # Add some variation based on where ball hits paddle
            hit_pos = (self.ball_y - self.player1_y) / self.paddle_height - 0.5
            self.ball_velocity_y += hit_pos * 10.0
        
        # Player 2 paddle (right)
        if (self.ball_x >= self.width - self.paddle_width - self.ball_size and 
            self.player2_y <= self.ball_y <= self.player2_y + self.paddle_height):
            self.ball_velocity_x = -abs(self.ball_velocity_x)
            # Add some variation based on where ball hits paddle
            hit_pos = (self.ball_y - self.player2_y) / self.paddle_height - 0.5
            self.ball_velocity_y += hit_pos * 10.0
        
        # Check for scoring
        if self.ball_x < 0:
            self.score_player2 += 1
            self._reset_ball()
        elif self.ball_x > self.width:
            self.score_player1 += 1
            self._reset_ball()
    
    def render(self):
        layers = []
        
        # Background
        layers.append(FillLayer(color=(0, 0, 0, 255)))
        
        # Center line
        for y in range(0, self.height, 4):
            layers.append(RectLayer(
                x=self.width // 2 - 0.5,
                y=y,
                width=1,
                height=2,
                color=(100, 100, 100, 255)
            ))
        
        # Player 1 paddle (left)
        layers.append(RectLayer(
            x=0,
            y=self.player1_y,
            width=self.paddle_width,
            height=self.paddle_height,
            color=(255, 255, 255, 255)
        ))
        
        # Player 2 paddle (right)
        layers.append(RectLayer(
            x=self.width - self.paddle_width,
            y=self.player2_y,
            width=self.paddle_width,
            height=self.paddle_height,
            color=(255, 255, 255, 255)
        ))
        
        # Ball
        layers.append(RectLayer(
            x=self.ball_x,
            y=self.ball_y,
            width=self.ball_size,
            height=self.ball_size,
            color=(255, 255, 255, 255)
        ))
        
        # Score text
        layers.append(TextLayer(
            text=f"{self.score_player1}",
            x=2,
            y=2,
            font_size=6,
            color=(255, 100, 100, 255)
        ))
        
        layers.append(TextLayer(
            text=f"{self.score_player2}",
            x=self.width - 8,
            y=2,
            font_size=6,
            color=(100, 100, 255, 255)
        ))
        
        return FrameDescription(
            width=self.width,
            height=self.height,
            layers=layers
        )
    
    def get_events(self):
        return [MovePlayer, ResetGame]
