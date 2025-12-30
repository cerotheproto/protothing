from fastapi import APIRouter, UploadFile, File, HTTPException, Response
from pathlib import Path
from typing import List, Optional
import shutil
import yaml
from pydantic import BaseModel

router = APIRouter()

ASSETS_ROOT = Path("assets")


class FileInfo(BaseModel):
    path: str
    name: str
    type: str  # "file", "directory", "image", "yaml"
    size: Optional[int] = None


class DirectoryListing(BaseModel):
    path: str
    items: List[FileInfo]


def get_file_type(path: Path) -> str:
    """Определяет тип файла"""
    if path.is_dir():
        return "directory"
    
    suffix = path.suffix.lower()
    if suffix in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
        return "image"
    elif suffix in ['.yaml', '.yml']:
        return "yaml"
    else:
        return "file"


def get_relative_path(full_path: Path) -> str:
    """Получает относительный путь от assets"""
    try:
        return str(full_path.relative_to(ASSETS_ROOT))
    except ValueError:
        return str(full_path)


@router.get("/list", response_model=DirectoryListing)
async def list_files(path: str = ""):
    """Получить список файлов в директории"""
    target_path = ASSETS_ROOT / path
    
    if not target_path.exists():
        raise HTTPException(status_code=404, detail="Директория не найдена")
    
    if not target_path.is_dir():
        raise HTTPException(status_code=400, detail="Путь не является директорией")
    
    # проверяем что путь внутри assets
    try:
        target_path.resolve().relative_to(ASSETS_ROOT.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    
    items = []
    for item in sorted(target_path.iterdir()):
        file_type = get_file_type(item)
        items.append(FileInfo(
            path=get_relative_path(item),
            name=item.name,
            type=file_type,
            size=item.stat().st_size if item.is_file() else None
        ))
    
    return DirectoryListing(
        path=path,
        items=items
    )


@router.get("/download")
async def download_file(path: str):
    """Скачать файл"""
    target_path = ASSETS_ROOT / path
    
    if not target_path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    
    if not target_path.is_file():
        raise HTTPException(status_code=400, detail="Путь не является файлом")
    
    # проверяем что путь внутри assets
    try:
        target_path.resolve().relative_to(ASSETS_ROOT.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    
    with open(target_path, "rb") as f:
        content = f.read()
    
    # определяем mime type
    suffix = target_path.suffix.lower()
    media_types = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.bmp': 'image/bmp',
        '.yaml': 'text/yaml',
        '.yml': 'text/yaml',
    }
    media_type = media_types.get(suffix, 'application/octet-stream')
    
    return Response(content=content, media_type=media_type)


@router.post("/upload")
async def upload_file(path: str, file: UploadFile = File(...)):
    """Загрузить файл"""
    target_path = ASSETS_ROOT / path / file.filename
    
    # проверяем что путь внутри assets
    try:
        target_path.resolve().parent.relative_to(ASSETS_ROOT.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    
    # создаем директорию если не существует
    target_path.parent.mkdir(parents=True, exist_ok=True)
    
    # сохраняем файл
    with open(target_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {
        "success": True,
        "path": get_relative_path(target_path),
        "name": file.filename
    }


@router.delete("/delete")
async def delete_file(path: str):
    """Удалить файл или директорию"""
    target_path = ASSETS_ROOT / path
    
    if not target_path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    
    # проверяем что путь внутри assets
    try:
        target_path.resolve().relative_to(ASSETS_ROOT.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    
    # не даем удалить корневую директорию assets
    if target_path.resolve() == ASSETS_ROOT.resolve():
        raise HTTPException(status_code=403, detail="Нельзя удалить корневую директорию")
    
    if target_path.is_dir():
        shutil.rmtree(target_path)
    else:
        target_path.unlink()
    
    return {"success": True}


@router.post("/create-directory")
async def create_directory(path: str, name: str):
    """Создать директорию"""
    target_path = ASSETS_ROOT / path / name
    
    # проверяем что путь внутри assets
    try:
        target_path.resolve().relative_to(ASSETS_ROOT.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    
    if target_path.exists():
        raise HTTPException(status_code=400, detail="Директория уже существует")
    
    target_path.mkdir(parents=True, exist_ok=True)
    
    return {
        "success": True,
        "path": get_relative_path(target_path)
    }


@router.get("/metadata")
async def get_metadata(path: str):
    """Получить содержимое yaml файла"""
    target_path = ASSETS_ROOT / path
    
    if not target_path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    
    if target_path.suffix.lower() not in ['.yaml', '.yml']:
        raise HTTPException(status_code=400, detail="Файл не является yaml")
    
    # проверяем что путь внутри assets
    try:
        target_path.resolve().relative_to(ASSETS_ROOT.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    
    with open(target_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    return data


@router.put("/metadata")
async def update_metadata(path: str, data: dict):
    """Обновить содержимое yaml файла"""
    target_path = ASSETS_ROOT / path
    
    if not target_path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    
    if target_path.suffix.lower() not in ['.yaml', '.yml']:
        raise HTTPException(status_code=400, detail="Файл не является yaml")
    
    # проверяем что путь внутри assets
    try:
        target_path.resolve().relative_to(ASSETS_ROOT.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    
    with open(target_path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)
    
    return {"success": True}
