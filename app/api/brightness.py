from fastapi import APIRouter, HTTPException
from dependencies import driver
router = APIRouter()

@router.post("/{level}")
async def set_brightness(level: int):
    if level < 0 or level > 255:
        raise HTTPException(status_code=400, detail="Brightness level must be between 0 and 255")
    await driver.set_brightness(level)
    return {"brightness": level}

@router.get("/")
async def get_brightness():
    brightness = await driver.get_brightness()
    return {"brightness": brightness}