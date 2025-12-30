from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Any
from render.frame_description import WiggleEffect
from dependencies import effect_manager
import inspect

router = APIRouter()


class AddEffectRequest(BaseModel):
    effect_name: str
    params: dict = {}


class AddEffectResponse(BaseModel):
    status: str
    effect_id: str
    effect_type: str
    message: str


class EffectInfo(BaseModel):
    id: str
    name: str


class EffectParamInfo(BaseModel):
    name: str
    type: str
    default: Any
    required: bool = False


class EffectMetadata(BaseModel):
    name: str
    params: list[EffectParamInfo]


@router.post("/add")
async def add_effect(request: AddEffectRequest = Body(...)):
    """Добавляет эффект в менеджер"""
    try:
        effect = effect_manager.add_effect_by_name(request.effect_name, **request.params)
        return AddEffectResponse(
            status="ok",
            effect_id=effect.id,
            effect_type=request.effect_name,
            message=f"Эффект {request.effect_name} добавлен"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка при добавлении эффекта: {str(e)}")


@router.delete("/clear")
async def clear_effects():
    """Очищает все эффекты"""
    effect_manager.clear_effects()
    return {"status": "ok", "message": "Все эффекты удалены"}


@router.delete("/{effect_id}")
async def remove_effect(effect_id: str):
    """Удаляет конкретный эффект по ID"""
    success = effect_manager.remove_effect_by_id(effect_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Эффект с ID {effect_id} не найден")
    return {"status": "ok", "message": f"Эффект {effect_id} удален"}


@router.get("/available")
async def get_available_effects():
    """Возвращает список доступных типов эффектов"""
    available = effect_manager.get_available_effects()
    return {
        "effects": available,
        "count": len(available)
    }


@router.get("/active")
async def get_active_effects():
    """Возвращает список активных эффектов"""
    effects = effect_manager.get_effects()
    return {
        "effects": [{"id": e.id, "name": type(e).__name__} for e in effects],
        "count": len(effects)
    }


@router.get("/metadata")
async def get_effects_metadata():
    """Возвращает метаданные всех эффектов (имена, параметры, типы)"""
    metadata = []
    
    for effect_name, effect_class in effect_manager._available_effects.items():
        params = []
        
        # получаем параметры из dataclass
        if hasattr(effect_class, '__dataclass_fields__'):
            for field_name, field_info in effect_class.__dataclass_fields__.items():
                # пропускаем внутренние поля и id
                if field_name.startswith('_') or field_name == 'id':
                    continue
                
                param_type = "string"
                if field_info.type == float:
                    param_type = "number"
                elif field_info.type == int:
                    param_type = "integer"
                elif field_info.type == bool:
                    param_type = "boolean"
                elif "tuple" in str(field_info.type):
                    # определяем, это tuple с int или нет
                    if "int" in str(field_info.type):
                        param_type = "color"
                    else:
                        param_type = "tuple"
                
                default_value = field_info.default if field_info.default is not inspect.Parameter.empty else None
                if default_value is None and hasattr(field_info, 'default_factory'):
                    default_value = None
                
                params.append({
                    "name": field_name,
                    "type": param_type,
                    "default": default_value,
                    "required": field_info.default is inspect.Parameter.empty
                })
        
        metadata.append({
            "name": effect_name,
            "params": params
        })
    
    return {"effects": metadata}
