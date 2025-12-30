# App development

## Overview
Apps are located in `app/apps/`. Each app is a folder with `app.py` containing the main class.

## Creating a new app
1. Create a folder `app/apps/your_app_name/`
2. Create `app.py` in that folder
3. In `app.py`, define a class inheriting from `BaseApp`

## BaseApp methods to implement
- `__init__()`: Initialize app state
- `start()`: Called when app becomes active
- `stop()`: Called when app is deactivated
- `update(dt, events)`: Update state each frame, handle events
- `render()`: Return `FrameDescription` or `Frame` for display
- `get_queries()`: Return list of query types the app handles
- `get_events()`: Return list of event types the app handles
- `handle_query(query)`: Process queries

## Rendering
Use `FrameDescription` with layers:
- `SpriteLayer`: Display images
- `TextLayer`: Display text
- `FillLayer`: Fill areas with color
- `AnimatedSpriteLayer`: For animations

Import from `render.frame_description`.

## Utils
Use helpers from `utils/`:
- `colors.py`: Color utilities
- `sprites.py`: Sprite handling
- `transition.py`: Transitions

## Assets
Store static files in `assets/your_app_name/`. Use `assets_manager` to load them.

## Effects
Use `effect_manager.py` for effects like rainbow, shake, etc.

## Example
```python
from apps.base import BaseApp
from render.frame_description import FrameDescription, TextLayer

class MyApp(BaseApp):
    name = "my_app"

    def render(self):
        return FrameDescription(layers=[
            TextLayer(text="Hello", position=(10, 10))
        ])
```

## Web UI
You can write custom web UI component for your app in `webui/src/components` and include it in `webui/src/app/events`.
Refer to `webui/src/components/ReactiveFacePage.tsx` for examples.

