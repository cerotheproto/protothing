import os
from PIL import Image
from apps.base import BaseApp
from apps.dino_game.events import JumpEvent, DuckEvent, RestartEvent
from models.app_contract import Event, Query, QueryResult
from render.frame_description import FrameDescription, SpriteLayer, TextLayer, FillLayer
from render.frame import Frame
import random

class DinoGameApp(BaseApp):
    name = "dino_game"

    def __init__(self):
        super().__init__()
        self.sprite_sheet_path = "assets/dino/offline-sprite-1x.png"
        self.sprites = {}
        self.scale = 0.25
        self.ground_y = 25 # Y position of the ground (bottom of dino)
        
        # Game state
        self.is_playing = False
        self.is_crashed = False
        self.score = 0
        self.high_score = 0
        self.speed = 50 # pixels per second
        self.distance = 0
        
        # Dino state
        self.dino_y = self.ground_y
        self.dino_y_velocity = 0
        self.gravity = 600
        self.jump_velocity = -180
        self.is_jumping = False
        self.is_ducking = False
        self.dino_state = "WAITING" # WAITING, RUNNING, JUMPING, DUCKING, CRASHED
        self.dino_frame_index = 0
        self.dino_frame_timer = 0
        
        # Objects
        self.obstacles = []
        self.clouds = []
        self.horizon_x = 0
        
        self.load_resources()

    def load_resources(self):
        if not os.path.exists(self.sprite_sheet_path):
            print(f"Error: Sprite sheet not found at {self.sprite_sheet_path}")
            return

        sheet = Image.open(self.sprite_sheet_path).convert("RGBA")
        
        def get_sprite(x, y, w, h):
            sprite = sheet.crop((x, y, x + w, y + h))
            new_size = (int(w * self.scale), int(h * self.scale))
            return sprite.resize(new_size, Image.NEAREST)

        # Sprite definitions (from source.js LDPI)
        # TREX base x: 677, y: 2
        trex_base_x = 677
        trex_y = 2
        trex_w = 44
        trex_h = 47
        trex_duck_w = 59
        
        self.sprites["trex_waiting_0"] = get_sprite(trex_base_x + 44, trex_y, trex_w, trex_h)
        self.sprites["trex_waiting_1"] = get_sprite(trex_base_x + 0, trex_y, trex_w, trex_h)
        self.sprites["trex_running_0"] = get_sprite(trex_base_x + 88, trex_y, trex_w, trex_h)
        self.sprites["trex_running_1"] = get_sprite(trex_base_x + 132, trex_y, trex_w, trex_h)
        self.sprites["trex_jumping"] = get_sprite(trex_base_x + 0, trex_y, trex_w, trex_h)
        self.sprites["trex_crashed"] = get_sprite(trex_base_x + 220, trex_y, trex_w, trex_h)
        self.sprites["trex_ducking_0"] = get_sprite(trex_base_x + 262, trex_y, trex_duck_w, trex_h)
        self.sprites["trex_ducking_1"] = get_sprite(trex_base_x + 321, trex_y, trex_duck_w, trex_h)

        # Obstacles
        # CACTUS_SMALL x: 228, y: 2
        self.sprites["cactus_small_0"] = get_sprite(228, 2, 17, 35)
        self.sprites["cactus_small_1"] = get_sprite(228 + 17, 2, 17, 35) # Assuming multiple
        self.sprites["cactus_small_2"] = get_sprite(228 + 34, 2, 17, 35)
        
        # CACTUS_LARGE x: 332, y: 2
        self.sprites["cactus_large_0"] = get_sprite(332, 2, 25, 50)
        self.sprites["cactus_large_1"] = get_sprite(332 + 25, 2, 25, 50)
        
        # PTERODACTYL x: 134, y: 2
        self.sprites["ptero_0"] = get_sprite(134, 2, 46, 40)
        self.sprites["ptero_1"] = get_sprite(134 + 46, 2, 46, 40)
        
        # CLOUD x: 86, y: 2
        self.sprites["cloud"] = get_sprite(86, 2, 46, 14)
        
        # HORIZON x: 2, y: 54
        self.sprites["horizon"] = get_sprite(2, 54, 600, 12)
        
        # RESTART x: 2, y: 2
        self.sprites["restart"] = get_sprite(2, 2, 36, 32)
        
        # Convert to bytes for SpriteLayer
        for key in self.sprites:
            img = self.sprites[key]
            self.sprites[key] = {
                "image": img.tobytes(),
                "width": img.width,
                "height": img.height
            }

    def get_events(self) -> list[type[Event]]:
        return [JumpEvent, DuckEvent, RestartEvent]

    def start(self):
        super().start()
        self.reset_game()

    def reset_game(self):
        self.is_playing = True
        self.is_crashed = False
        self.score = 0
        self.distance = 0
        self.speed = 100
        self.dino_y = self.ground_y
        self.dino_y_velocity = 0
        self.is_jumping = False
        self.is_ducking = False
        self.dino_state = "RUNNING"
        self.obstacles = []
        self.clouds = []
        self.horizon_x = 0

    def update(self, dt: float, events: list[Event]):
        for event in events:
            if isinstance(event, RestartEvent):
                self.reset_game()
            elif isinstance(event, JumpEvent):
                if not self.is_playing and self.is_crashed:
                    self.reset_game()
                elif self.is_playing and not self.is_jumping and not self.is_crashed:
                    self.is_jumping = True
                    self.dino_y_velocity = self.jump_velocity
                    self.dino_state = "JUMPING"
            elif isinstance(event, DuckEvent):
                if self.is_playing and not self.is_crashed:
                    self.is_ducking = not self.is_ducking
                    if not self.is_jumping:
                        self.dino_state = "DUCKING" if self.is_ducking else "RUNNING"

        if not self.is_playing:
            return

        # Update Dino
        if self.is_jumping:
            self.dino_y += self.dino_y_velocity * dt
            self.dino_y_velocity += self.gravity * dt
            
            if self.dino_y >= self.ground_y:
                self.dino_y = self.ground_y
                self.is_jumping = False
                self.dino_y_velocity = 0
                self.dino_state = "DUCKING" if self.is_ducking else "RUNNING"
        
        # Animation
        self.dino_frame_timer += dt
        frame_duration = 0.1
        if self.dino_state == "RUNNING":
            if self.dino_frame_timer > frame_duration:
                self.dino_frame_index = (self.dino_frame_index + 1) % 2
                self.dino_frame_timer = 0
        elif self.dino_state == "DUCKING":
            if self.dino_frame_timer > frame_duration:
                self.dino_frame_index = (self.dino_frame_index + 1) % 2
                self.dino_frame_timer = 0
        else:
            self.dino_frame_index = 0

        # Move world
        move_dist = self.speed * dt
        self.distance += move_dist
        self.score = int(self.distance / 10)
        self.speed += dt * 2 # Accelerate slowly
        
        self.horizon_x = (self.horizon_x - move_dist) % self.sprites["horizon"]["width"]

        # Obstacles
        # Spawn
        spawn_dist = random.randint(int(60 * self.scale / 0.5), int(150 * self.scale / 0.5))
        if not self.obstacles or (64 - self.obstacles[-1]["x"] > spawn_dist):
            if random.random() < 0.05:
                type_ = random.choice(["cactus_small", "cactus_large", "ptero"])
                if type_ == "cactus_small":
                    sprite_key = f"cactus_small_{random.randint(0, 2)}"
                    y = self.ground_y
                elif type_ == "cactus_large":
                    sprite_key = f"cactus_large_{random.randint(0, 1)}"
                    y = self.ground_y
                else:
                    sprite_key = "ptero"
                    y = self.ground_y - random.randint(int(10 * self.scale / 0.5), int(20 * self.scale / 0.5))
                
                # Get width/height from sprite
                if sprite_key == "ptero":
                    s = self.sprites["ptero_0"]
                else:
                    s = self.sprites[sprite_key]
                    
                self.obstacles.append({
                    "type": type_,
                    "sprite": sprite_key,
                    "x": 80, # Spawn off screen
                    "y": y,
                    "width": s["width"],
                    "height": s["height"],
                    "frame": 0,
                    "timer": 0
                })

        # Update obstacles
        for obs in self.obstacles:
            obs["x"] -= move_dist
            
            # Ptero animation
            if obs["type"] == "ptero":
                obs["timer"] += dt
                if obs["timer"] > 0.2:
                    obs["frame"] = (obs["frame"] + 1) % 2
                    obs["timer"] = 0

        self.obstacles = [o for o in self.obstacles if o["x"] + o["width"] > -10]

        # Collision
        dino_sprite_key = self._get_dino_sprite_key()
        dino_s = self.sprites[dino_sprite_key]
        dino_x = 2
        # Scale hitbox offsets with the sprites
        off_d = max(1, int(4 * self.scale / 0.5))
        dino_rect = (dino_x + off_d, self.dino_y - dino_s["height"] + off_d, dino_s["width"] - off_d*2, dino_s["height"] - off_d*2)
        
        for obs in self.obstacles:
            off_o = max(1, int(2 * self.scale / 0.5))
            obs_rect = (obs["x"] + off_o, obs["y"] - obs["height"] + off_o, obs["width"] - off_o*2, obs["height"] - off_o*2)
            
            if (dino_rect[0] < obs_rect[0] + obs_rect[2] and
                dino_rect[0] + dino_rect[2] > obs_rect[0] and
                dino_rect[1] < obs_rect[1] + obs_rect[3] and
                dino_rect[1] + dino_rect[3] > obs_rect[1]):
                
                self.crash()
                break

    def crash(self):
        self.is_playing = False
        self.is_crashed = True
        self.dino_state = "CRASHED"
        if self.score > self.high_score:
            self.high_score = self.score

    def _get_dino_sprite_key(self):
        if self.dino_state == "CRASHED":
            return "trex_crashed"
        elif self.dino_state == "JUMPING":
            return "trex_jumping"
        elif self.dino_state == "DUCKING":
            return f"trex_ducking_{self.dino_frame_index}"
        elif self.dino_state == "RUNNING":
            return f"trex_running_{self.dino_frame_index}"
        else:
            return f"trex_waiting_{self.dino_frame_index}"

    def render(self) -> FrameDescription:
        layers = []
        
        # Background
        layers.append(FillLayer(color=(247, 247, 247, 255)))
        
        # Horizon
        h_sprite = self.sprites["horizon"]
        # Draw twice for scrolling
        layers.append(SpriteLayer(
            image=h_sprite["image"],
            sprite_width=h_sprite["width"],
            sprite_height=h_sprite["height"],
            x=self.horizon_x,
            y=self.ground_y - h_sprite["height"] + 1
        ))
        layers.append(SpriteLayer(
            image=h_sprite["image"],
            sprite_width=h_sprite["width"],
            sprite_height=h_sprite["height"],
            x=self.horizon_x + h_sprite["width"],
            y=self.ground_y - h_sprite["height"] + 1
        ))
        
        # Obstacles
        for obs in self.obstacles:
            key = obs["sprite"]
            if obs["type"] == "ptero":
                key = f"ptero_{obs['frame']}"
            
            s = self.sprites[key]
            layers.append(SpriteLayer(
                image=s["image"],
                sprite_width=s["width"],
                sprite_height=s["height"],
                x=obs["x"],
                y=obs["y"] - s["height"] # Anchor bottom-left
            ))
            
        # Dino
        dino_key = self._get_dino_sprite_key()
        dino_s = self.sprites[dino_key]
        layers.append(SpriteLayer(
            image=dino_s["image"],
            sprite_width=dino_s["width"],
            sprite_height=dino_s["height"],
            x=10,
            y=self.dino_y - dino_s["height"] # Anchor bottom-left
        ))
        
        # Score
        layers.append(TextLayer(
            text=f"{self.score:05d}",
            x=40,
            y=2,
            font_size=8,
            color=(83, 83, 83, 255)
        ))
        
        if self.is_crashed:
             restart_s = self.sprites["restart"]
             layers.append(SpriteLayer(
                image=restart_s["image"],
                sprite_width=restart_s["width"],
                sprite_height=restart_s["height"],
                x=32 - restart_s["width"] / 2,
                y=16 - restart_s["height"] / 2
            ))

        return FrameDescription(
            width=64,
            height=32,
            layers=layers
        )
