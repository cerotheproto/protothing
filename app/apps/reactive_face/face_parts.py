from dataclasses import dataclass
from render.frame_description import SpriteLayer, AnimatedSpriteLayer
from typing import Union, Literal
import yaml
import os


FacePartType = Literal["eye", "nose", "mouth"]
StateType = Union[SpriteLayer, AnimatedSpriteLayer]


@dataclass
class PartState:
    """Состояние отдельной части лица"""
    name: str
    layer: StateType
    

@dataclass
class FacePart:
    """Часть лица с несколькими состояниями"""
    part_type: FacePartType
    ref: str
    position_x: int
    position_y: int
    states: dict[str, PartState]
    default_state: str = "default"
    animated: bool = False
    
    def get_state(self, state_name: str) -> PartState:
        """Получить состояние по названию"""
        if state_name not in self.states:
            return self.states[self.default_state]
        return self.states[state_name]


@dataclass
class FacePreset:
    """Пресет конфигурации лица с частями и их состояниями"""
    name: str
    parts: dict[FacePartType, tuple[str, str]]  # тип -> (ref, state)
    
    def to_dict(self) -> dict:
        """Преобразовать в словарь для сохранения"""
        return {
            "name": self.name,
            "components": {
                part_type: {
                    "ref": ref,
                    "state": state
                }
                for part_type, (ref, state) in self.parts.items()
            }
        }


def load_face_part(
    part_type: FacePartType,
    ref: str,
    assets_dir: str = "assets/reactive_face"
) -> FacePart:
    """Загружает часть лица из метаданных и ассетов"""
    from utils.sprites import load_sprite, load_animated_sprite
    
    part_dir = os.path.join(assets_dir, part_type + "s", ref)
    metadata_path = os.path.join(part_dir, "metadata.yaml")
    
    # Обработка опечатки в названии файла (eyes/basic1/metаdata.yaml)
    if not os.path.exists(metadata_path):
        alt_metadata_path = os.path.join(part_dir, "metаdata.yaml")
        if os.path.exists(alt_metadata_path):
            metadata_path = alt_metadata_path
    
    if not os.path.exists(metadata_path):
        raise FileNotFoundError(f"Metadata for {part_type} '{ref}' not found: {metadata_path}")
    
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = yaml.safe_load(f)
    
    position_x = metadata.get("position", {}).get("x", 0)
    position_y = metadata.get("position", {}).get("y", 0)
    animated = metadata.get("animated", False)
    
    states_data = metadata.get("states", {})
    states = {}
    default_state = None
    
    for state_name, state_info in states_data.items():
        state_type = state_info.get("type", "sprite")
        asset_file = state_info.get("asset", "")
        asset_path = os.path.join(part_dir, asset_file)
        
        if not os.path.exists(asset_path):
            raise FileNotFoundError(f"Asset not found: {asset_path}")
        
        if state_type == "sprite":
            layer = load_sprite(asset_path, x=position_x, y=position_y)
        elif state_type == "animated_sprite":
            layer = load_animated_sprite(asset_path, x=position_x, y=position_y)
        else:
            raise ValueError(f"Unknown layer type: {state_type}")
        
        states[state_name] = PartState(name=state_name, layer=layer)
        
        if default_state is None:
            default_state = state_name
    
    return FacePart(
        part_type=part_type,
        ref=ref,
        position_x=position_x,
        position_y=position_y,
        states=states,
        default_state=default_state or "default",
        animated=animated
    )


def load_face_preset(
    preset_name: str,
    assets_dir: str = "assets/reactive_face"
) -> FacePreset:
    """Загружает пресет лица из конфигурации"""
    preset_path = os.path.join(assets_dir, "presets", f"{preset_name}.yaml")
    
    if not os.path.exists(preset_path):
        raise FileNotFoundError(f"Preset not found: {preset_path}")
    
    with open(preset_path, 'r', encoding='utf-8') as f:
        preset_data = yaml.safe_load(f)
    
    preset_name_from_file = preset_data.get("name", preset_name)
    components = preset_data.get("components", {})
    
    parts = {}
    for component_type, component_config in components.items():
        part_type: FacePartType = component_type
        ref = component_config.get("ref", "")
        state = component_config.get("state", "default")
        parts[part_type] = (ref, state)
    
    return FacePreset(name=preset_name_from_file, parts=parts)


class FacePartsCache:
    """Кеш загруженных частей лица для оптимизации"""
    
    def __init__(self, assets_dir: str = "assets/reactive_face"):
        self.assets_dir = assets_dir
        self.parts_cache: dict[tuple[FacePartType, str], FacePart] = {}
        self.presets_cache: dict[str, FacePreset] = {}
    
    def get_part(self, part_type: FacePartType, ref: str) -> FacePart:
        """Получить часть лица с кешированием"""
        key = (part_type, ref)
        if key not in self.parts_cache:
            self.parts_cache[key] = load_face_part(part_type, ref, self.assets_dir)
        return self.parts_cache[key]
    
    def get_preset(self, preset_name: str) -> FacePreset:
        """Получить пресет с кешированием"""
        if preset_name not in self.presets_cache:
            self.presets_cache[preset_name] = load_face_preset(preset_name, self.assets_dir)
        return self.presets_cache[preset_name]
    
    def clear(self):
        """Очистить кеш"""
        self.parts_cache.clear()
        self.presets_cache.clear()
    
    def reload_metadata(self):
        """Перезагружает все метаданные из хранилища"""
        self.clear()
    
    def get_all_parts_metadata(self) -> dict[str, list[dict]]:
        """Возвращает все доступные части лица сгруппированные по типам"""
        import os
        result: dict[str, list[dict]] = {}
        
        part_types = ["eye", "nose", "mouth"]
        
        for part_type in part_types:
            parts_dir = os.path.join(self.assets_dir, part_type + "s")
            if not os.path.exists(parts_dir):
                continue
            
            parts_list = []
            for ref in os.listdir(parts_dir):
                ref_path = os.path.join(parts_dir, ref)
                if not os.path.isdir(ref_path):
                    continue
                
                try:
                    face_part = self.get_part(part_type, ref)
                    parts_list.append({
                        "ref": ref,
                        "states": list(face_part.states.keys()),
                        "default_state": face_part.default_state,
                        "animated": face_part.animated
                    })
                except Exception:
                    continue
            
            if parts_list:
                result[part_type] = parts_list
        
        return result

    def get_all_presets(self) -> list[str]:
        """Возвращает список всех доступных пресетов"""
        import os
        presets_dir = os.path.join(self.assets_dir, "presets")
        
        if not os.path.exists(presets_dir):
            return []
        
        presets = []
        for filename in os.listdir(presets_dir):
            if filename.endswith(".yaml"):
                preset_name = filename[:-5]  # Удаляем расширение .yaml
                presets.append(preset_name)
        
        return sorted(presets)
