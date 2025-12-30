from fastapi import APIRouter
from dependencies import config

config_router = APIRouter()

@config_router.post("/reload")
async def reload_config():
    config.load()
    return {"status": "ok"}

