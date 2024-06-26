from fastapi import Depends, APIRouter, HTTPException
from sqlalchemy.orm import Session
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from typing import List
from src.auth.dependencies import (
    get_current_active_user,
    has_admin_role,
    has_access_to_tenant,
    has_access_to_device,
    has_admin_or_owner_role,
    can_edit_device
)
from src.user.schemas import User
from src.tenant.router import router as tenant_router
from ..database import get_db
from . import service, schemas

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("/", response_model=schemas.Device)
def register_device(
    device: schemas.DeviceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(has_admin_or_owner_role),
):
    db_device = service.create_device(db=db, device=device)
    return db_device


@router.get("/{device_id}", response_model=schemas.Device)
def read_device(
    device_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(has_access_to_device),
):
    db_device = service.get_device(db, device_id=device_id)
    return db_device


@tenant_router.get("/{tenant_id}/devices", response_model=Page[schemas.DeviceList])
def read_devices(
    tenant_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(has_access_to_tenant),
):
    return paginate(service.get_devices(db, tenant_id=tenant_id))


@router.get("/", response_model=Page[schemas.DeviceList])
def read_devices(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    return paginate(db, service.get_devices(db, user.id))


@router.patch("/{device_id}", response_model=schemas.Device)
def update_device(
    device_id: int,
    device: schemas.DeviceUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(can_edit_device),
):
    db_device = read_device(device_id, db)
    updated_device = service.update_device(db, db_device, updated_device=device)

    return updated_device


@router.delete("/{device_id}", response_model=schemas.DeviceDelete)
def delete_device(
    device_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(can_edit_device),
):
    db_device = read_device(device_id, db)
    deleted_device_id = service.delete_device(db, db_device)

    return {
        "id": deleted_device_id,
        "msg": f"Device {deleted_device_id} removed succesfully!",
    }
