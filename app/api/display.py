from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from display_manager import MirrorMode
from dependencies import display_manager


router = APIRouter()


class SetMirrorModeRequest(BaseModel):
    mode: str


@router.post("/mirror")
async def set_mirror_mode(request: SetMirrorModeRequest):
    """Устанавливает режим отражения (none, left, right)"""
    try:
        mode = MirrorMode(request.mode)
        display_manager.set_mirror_mode(mode)
        return {
            "status": "ok",
            "mirror_mode": request.mode,
            "message": f"Режим отражения установлен на '{request.mode}'"
        }
    except ValueError:
        valid_modes = [m.value for m in MirrorMode]
        raise HTTPException(
            status_code=400,
            detail=f"Неизвестный режим отражения. Допустимые значения: {valid_modes}"
        )


@router.get("/mirror")
async def get_mirror_mode():
    """Возвращает текущий режим отражения"""
    return {
        "mirror_mode": display_manager.mirror_mode.value
    }
