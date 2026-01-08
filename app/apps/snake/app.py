import numpy as np
import logging
from apps.base import BaseApp
from models.app_contract import Event
from render.frame_description import FrameDescription, RectLayer, FillLayer, TextLayer
from apps.snake.events import MoveSnake, ResetSnakeGame

logger = logging.getLogger(__name__)


class SnakeApp(BaseApp):
    name = "snake"
    
    def __init__(self):
        super().__init__()
        
        # Game field dimensions
        self.width = 64
        self.height = 32
        
        # Snake segment size
        self.segment_size = 1
        
        # Game state
        self.snake_body = [(self.width // 2, self.height // 2)]
        self.direction = 3  # 0 - up, 1 - down, 2 - left, 3 - right
        self.next_direction = 3
        self.snake_speed = 8.0  # pixels per second
        self.move_timer = 0.0
        self.move_interval = 1.0 / self.snake_speed
        
        # Food
        self.food_x = None
        self.food_y = None
        
        # Score and game state
        self.score = 0
        self.game_over = False
    
    def start(self):
        super().start()
        self._spawn_food()

    def stop(self):
        super().stop()
        self._reset_game()

    def _spawn_food(self):
        """Spawn food at random position not occupied by snake"""
        while True:
            self.food_x = np.random.randint(0, self.width)
            self.food_y = np.random.randint(0, self.height)
            if (self.food_x, self.food_y) not in self.snake_body:
                break
    
    def update(self, dt: float, events: list[Event]):
        # Handle events
        for event in events:
            if isinstance(event, MoveSnake):
                self.next_direction = event.direction
            elif isinstance(event, ResetSnakeGame):
                self._reset_game()
        
        if self.game_over:
            return
        
        # Update movement timer
        self.move_timer += dt
        
        # Move snake when timer exceeds interval
        if self.move_timer >= self.move_interval:
            self.move_timer = 0.0
            
            # Only allow direction change if not opposite
            if not self._is_opposite_direction(self.next_direction, self.direction):
                self.direction = self.next_direction
            
            # Get head position
            head_x, head_y = self.snake_body[0]
            
            # Calculate new head position based on direction
            if self.direction == 0:  # up
                head_y -= 1
            elif self.direction == 1:  # down
                head_y += 1
            elif self.direction == 2:  # left
                head_x -= 1
            elif self.direction == 3:  # right
                head_x += 1
            
            # Check wall collision
            if head_x < 0 or head_x >= self.width or head_y < 0 or head_y >= self.height:
                self.game_over = True
                return
            
            # Check self collision
            if (head_x, head_y) in self.snake_body:
                self.game_over = True
                return
            
            # Add new head
            self.snake_body.insert(0, (head_x, head_y))
            
            # Check food collision
            if head_x == self.food_x and head_y == self.food_y:
                self.score += 1
                self._spawn_food()
            else:
                # Remove tail if no food eaten
                self.snake_body.pop()
    
    def _is_opposite_direction(self, new_dir: int, current_dir: int) -> bool:
        """Check if new direction is opposite to current direction"""
        opposites = {0: 1, 1: 0, 2: 3, 3: 2}  # up-down, left-right
        return new_dir == opposites.get(current_dir, -1)
    
    def _reset_game(self):
        """Reset game state"""
        self.snake_body = [(self.width // 2, self.height // 2)]
        self.direction = 3
        self.next_direction = 3
        self.move_timer = 0.0
        self.score = 0
        self.game_over = False
        self._spawn_food()
    
    def render(self):
        layers = []
        
        # Background
        layers.append(FillLayer(color=(0, 0, 0, 255)))
        
        # Food
        if self.food_x is not None and self.food_y is not None:
            layers.append(RectLayer(
                x=self.food_x,
                y=self.food_y,
                width=self.segment_size,
                height=self.segment_size,
                color=(255, 100, 100, 255)
            ))
        
        # Snake body (tail to head, so head is drawn last)
        for i, (x, y) in enumerate(self.snake_body):
            if i == 0:  # Head
                color = (100, 255, 100, 255)
            else:  # Body
                color = (100, 200, 100, 255)
            
            layers.append(RectLayer(
                x=x,
                y=y,
                width=self.segment_size,
                height=self.segment_size,
                color=color
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
                x=self.width // 2 - 20,
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
        return [MoveSnake, ResetSnakeGame]
