from sqlalchemy.orm import Session
from typing import Union
from src.auth.dependencies import has_access_to_tenant
from src.exceptions import PermissionDenied
from src.tag import service as tags_service
from src.tag import models as tag_models
from src.user.schemas import User
from src.user.models import tenants_and_users_table
from src.tenant import schemas, models
from src.tenant import exceptions
from src.tenant.utils import check_tenant_exists, check_tenant_name_taken
from src.entity.service import create_entity_auto


def get_tenant(db: Session, tenant_id: int):
    check_tenant_exists(db, tenant_id)
    return db.query(models.Tenant).filter(models.Tenant.id == tenant_id).first()


def get_tenants(db: Session, user: User):
    tenants = db.query(models.Tenant)
    if user.role_id != 1:
        tenants = tenants.join(tenants_and_users_table).filter(
            models.Tenant.id == tenants_and_users_table.c.tenant_id,
            user.id == tenants_and_users_table.c.user_id,
        )
    return tenants


def get_tenant_by_name(db: Session, tenant_name: str):
    db_tenant = (
        db.query(models.Tenant).filter(models.Tenant.name == tenant_name).first()
    )
    if not db_tenant:
        raise exceptions.TenantNotFound()
    return db_tenant


def create_tenant(db: Session, tenant: schemas.TenantCreate):
    check_tenant_name_taken(db, tenant.name)

    entity = create_entity_auto(db)
    db_tenant = models.Tenant(**tenant.model_dump(), entity_id=entity.id)
    db.add(db_tenant)
    db.commit()
    db.refresh(db_tenant)
    return db_tenant


def update_tenant(
    db: Session,
    db_tenant: schemas.Tenant,
    updated_tenant: schemas.TenantUpdate,
):
    # sanity checks
    check_tenant_exists(db, db_tenant.id)
    check_tenant_name_taken(db, updated_tenant.name)

    db.query(models.Tenant).filter(models.Tenant.id == db_tenant.id).update(
        values=updated_tenant.model_dump()
    )

    db.commit()
    db.refresh(db_tenant)
    return db_tenant


def delete_tenant(db: Session, db_tenant: schemas.Tenant):
    # sanity check
    check_tenant_exists(db, tenant_id=db_tenant.id)

    db.delete(db_tenant)
    db.commit()
    return db_tenant.id


async def get_tenant_tags(
    db: Session,
    user: User,
    tenant_id: Union[int, None] = None,
):
    check_tenant_exists(db, tenant_id)
    if await has_access_to_tenant(tenant_id, db, user):
        return (
            db.query(tag_models.Tag)
            .join(models.Tenant)
            .filter(models.Tenant.id == tenant_id)
            .filter(tag_models.Tag.tenant_id == tenant_id)
        )
    else:
        raise PermissionDenied()
