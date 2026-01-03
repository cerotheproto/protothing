# Генератор API роутеров на основе контракта приложений
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Any
import asyncio
from apps.base import BaseApp
from models.app_contract import Query, Event

# глобальная очередь событий
event_queue: asyncio.Queue[Event] = asyncio.Queue()

# реестр типов событий по имени
_event_registry: dict[str, type[Event]] = {}


def register_event_type(event_class: type[Event]):
    """Регистрирует тип события для использования через универсальный API"""
    _event_registry[event_class.__name__] = event_class


def get_event_class(name: str) -> type[Event] | None:
    """Возвращает класс события по имени"""
    return _event_registry.get(name)


def create_events_router() -> APIRouter:
    """Создает роутер для работы с событиями"""
    router = APIRouter()
    
    @router.post("/emit/{event_name}")
    async def emit_event(event_name: str, payload: dict = Body(default={})):
        """Отправляет событие в очередь"""
        event_class = get_event_class(event_name)
        if event_class is None:
            raise HTTPException(status_code=404, detail=f"Event '{event_name}' is not registered")
        
        try:
            event = event_class.model_validate(payload)
            await event_queue.put(event)
            return {"status": "ok", "event": event_name}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    def _collect_by_app() -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
        """Собирает события и запросы по приложениям в формате:
        ({app_name: [ {name, schema}, ... ]}, {app_name: [ {name, schema}, ... ]})
        """
        events_by_app: dict[str, list[dict]] = {}
        queries_by_app: dict[str, list[dict]] = {}

        from dependencies import app_manager as _app_manager
        for app in _app_manager.get_available_apps():
            app_name = app.name
            evs = []
            for ev in app.get_events():
                evs.append({
                    "name": ev.__name__,
                    "schema": ev.model_json_schema()
                })
            qrs = []
            for q in app.get_queries():
                qrs.append({
                    "name": q.__name__,
                    "description": q.__doc__,
                    "schema": q.model_json_schema()
                })
            if evs:
                events_by_app[app_name] = evs
            if qrs:
                queries_by_app[app_name] = qrs

        return events_by_app, queries_by_app

    @router.get("/types")
    async def get_event_types():
        """Возвращает зарегистрированные типы событий и запросов, сгруппированные по приложениям"""
        events_by_app, queries_by_app = _collect_by_app()
        return {
            "events": events_by_app,
            "queries": queries_by_app
        }

    @router.get("/types/{app_name}")
    async def get_event_types_for_app(app_name: str):
        """Возвращает типы событий и запросов для конкретного приложения"""
        events_by_app, queries_by_app = _collect_by_app()
        if app_name not in events_by_app and app_name not in queries_by_app:
            raise HTTPException(status_code=404, detail=f"Приложение '{app_name}' не найдено или не содержит типов")
        return {
            "events": events_by_app.get(app_name, []),
            "queries": queries_by_app.get(app_name, [])
        }
    
    return router


def generate_app_router(app: BaseApp) -> APIRouter:
    """Генерирует API роутер для приложения на основе его запросов"""
    router = APIRouter()
    
    # генерируем эндпоинты для запросов
    for query_class in app.get_queries():
        _register_query_endpoint(router, app, query_class)
    
    # мета-эндпоинт со списком доступных запросов — удалён, см. /events/types
    return router


def _register_query_endpoint(router: APIRouter, app: BaseApp, query_class: type[Query]):
    """Регистрирует эндпоинт для запроса"""
    query_name = query_class.__name__
    fields = query_class.model_fields
    
    if fields:
        schema = query_class.model_json_schema()
        
        async def query_handler_with_params(payload: dict = Body(...)):
            query = query_class.model_validate(payload)
            try:
                return app.handle_query(query)
            except NotImplementedError as e:
                raise HTTPException(status_code=501, detail=str(e))
        
        query_handler_with_params.__name__ = f"query_{query_name}"
        query_handler_with_params.__doc__ = query_class.__doc__ or f"Запрос {query_name}"
        
        router.add_api_route(
            f"/queries/{query_name}",
            query_handler_with_params,
            methods=["POST"],
            summary=f"Запрос: {query_name}",
            openapi_extra={"requestBody": {"content": {"application/json": {"schema": schema}}}}
        )
    else:
        async def query_handler():
            try:
                return app.handle_query(query_class())
            except NotImplementedError as e:
                raise HTTPException(status_code=501, detail=str(e))
        
        query_handler.__name__ = f"query_{query_name}"
        query_handler.__doc__ = query_class.__doc__ or f"Запрос {query_name}"
        
        router.add_api_route(
            f"/queries/{query_name}",
            query_handler,
            methods=["GET"],
            summary=f"Запрос: {query_name}"
        )


def _get_schema_info(model_class: type[BaseModel]) -> dict[str, Any]:
    """Возвращает информацию о схеме модели"""
    return {
        "name": model_class.__name__,
        "description": model_class.__doc__,
        "schema": model_class.model_json_schema()
    }
