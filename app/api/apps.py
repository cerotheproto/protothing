from fastapi import APIRouter, HTTPException
from dependencies import app_manager
app_router = APIRouter()

@app_router.get("/active")
async def get_active_app():
    active_app = app_manager.get_current_app()
    if active_app:
        return {"active_app": active_app.name}
    else:
        return {"active_app": None}
    
@app_router.post("/activate/{app_name}")
async def activate_app(app_name: str):
    if app_manager.set_active_app_by_name(app_name):
        return {"status": "ok", "active_app": app_name}
    else:
        raise HTTPException(status_code=404, detail="App not found") 
    
@app_router.get("/available")
async def get_available_apps():
    apps = app_manager.get_available_apps()
    return {"available_apps": [app.name for app in apps]}

