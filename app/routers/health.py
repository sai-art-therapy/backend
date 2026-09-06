import os
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import (
    YOLO_HTP_HOUSE_WEIGHTS_PATH,
    YOLO_HTP_PERSON_WEIGHTS_PATH,
    YOLO_HTP_TREE_WEIGHTS_PATH,
)
from app.db.session import engine


router = APIRouter()

MIN_FREE_DISK_BYTES = 1024 * 1024 * 1024
MODEL_WEIGHT_PATHS = (
    YOLO_HTP_HOUSE_WEIGHTS_PATH,
    YOLO_HTP_TREE_WEIGHTS_PATH,
    YOLO_HTP_PERSON_WEIGHTS_PATH,
)


def _database_is_ready() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False


def _models_are_ready() -> bool:
    return all(
        Path(model_path).is_file() and Path(model_path).stat().st_size > 1024
        for model_path in MODEL_WEIGHT_PATHS
    )


def _storage_is_ready() -> bool:
    upload_root = Path("uploads")
    storage_path = upload_root if upload_root.exists() else Path(".")
    try:
        return (
            os.access(storage_path, os.W_OK)
            and shutil.disk_usage(storage_path).free >= MIN_FREE_DISK_BYTES
        )
    except OSError:
        return False


def get_readiness_checks() -> dict[str, bool]:
    return {
        "database": _database_is_ready(),
        "models": _models_are_ready(),
        "storage": _storage_is_ready(),
    }


@router.get("/live", summary="프로세스 생존 확인")
def liveness():
    return {"status": "alive"}


@router.get("/ready", summary="서비스 준비 상태 확인")
def readiness():
    checks = get_readiness_checks()
    if not all(checks.values()):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not_ready", "checks": checks},
        )
    return {"status": "ready", "checks": checks}
