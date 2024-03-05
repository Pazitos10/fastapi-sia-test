from sqlalchemy.orm import Session
from typing import Union
from src.auth.dependencies import has_role
from src.user.schemas import User
from src.user import models as user_models
from src.tenant import models as tenant_models
from src.folder import models as folder_models
from src.device import models as device_models
from . import schemas, models


def get_tag_by_name(db: Session, tag_name: str):
    tag = db.query(models.Tag).filter(models.Tag.name == tag_name).first()
    if not tag:
        raise TagNotFoundError()
    return tag


def get_tag(db: Session, tag_id: int):
    tag = db.query(models.Tag).filter(models.Tag.id == tag_id).first()
    if not tag:
        raise TagNotFoundError()
    return tag


def get_entity_id(db, model, obj_id):
    # some objects with obj_id may not exist so we return None instead 
    # otherwise, the first value in the results tuple is returned
    entity_id = db.query(model.entity_id).filter(model.id == obj_id).first()
    return entity_id[0] if entity_id else None


def get_tags(
    db: Session,
    user: User,
    name: Union[str, None] = "",
    user_id: Union[int, None] = None,
    tenant_id: Union[int, None] = None,
    folder_id: Union[int, None] = None,
    device_id: Union[int, None] = None,
):
    filters = []

    user_entity_id = get_entity_id(db, user_models.User, user_id)
    tenant_entity_id = get_entity_id(db, tenant_models.Tenant, tenant_id)
    folder_entity_id = get_entity_id(db, folder_models.Folder, folder_id)
    device_entity_id = get_entity_id(db, device_models.Device, device_id)

    entity_ids = [user_entity_id, tenant_entity_id, folder_entity_id, device_entity_id]
    # adding filters conditionally
    if entity_ids and any(entity_ids):
        filters.append(models.entities_and_tags_table.columns.entity_id.in_(entity_ids))

    if name:
        name = f"%{name}%"
        filters.append(models.Tag.name.like(name))

    return db.query(models.Tag).join(models.entities_and_tags_table).filter(*filters)


def create_tag(db: Session, tag: schemas.TagCreate):
    # TODO: definir bien los campos de esta entidad. cuales son obligatorios y/o unicos para chequear restricciones
    # check_tag_exist(db, tag.tag_group_id)

    db_tag = models.tag(**tag.model_dump())
    db.add(db_tag)
    db.commit()
    db.refresh(db_tag)
    return db_tag


def update_tag(db: Session, db_tag: schemas.Tag, updated_tag: schemas.TagUpdate):
    get_tag(db, db_tag.id)

    db.query(models.tag).filter(models.tag.id == db_tag.id).update(
        values=updated_tag.model_dump()
    )
    db.commit()
    db.refresh(db_tag)
    return db_tag


def delete_tag(db: Session, db_tag: schemas.Tag):
    get_tag(db, db_tag.id)

    db.delete(db_tag)
    db.commit()
    return db_tag.id