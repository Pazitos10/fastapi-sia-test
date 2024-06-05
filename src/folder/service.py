from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from typing import List, Optional
from src.exceptions import PermissionDenied
from src.entity.service import create_entity_auto, update_entity_tags
from src.folder import exceptions, schemas, models
from src.auth.dependencies import has_role
from src.tag.service import create_tag
from src.tag.schemas import TagCreate
from src.tenant.service import check_tenant_exists
from src.tenant.models import tenants_and_users_table
from src.tenant.utils import filter_tag_ids
from src.user.models import User
from src.user.exceptions import UserTenantNotAssigned
from src.user.service import get_user


def check_folder_exist(db: Session, folder_id: int):
    db_folder = db.query(models.Folder).filter(models.Folder.id == folder_id).first()
    if not db_folder:
        raise exceptions.FolderNotFound()


def check_folder_name_taken(
    db: Session, folder_name: str, tenant_id: int, folder_id: Optional[int] = None
):
    folder_name_taken = db.query(models.Folder).filter(
        models.Folder.name == folder_name, models.Folder.tenant_id == tenant_id
    )

    if folder_id:
        folder_name_taken = folder_name_taken.filter(models.Folder.id != folder_id)

    if folder_name_taken.first():
        raise exceptions.FolderNameTaken()


def create_root_folder(db: Session, tenant_id: int):
    folder = schemas.FolderCreate(name="/", tenant_id=tenant_id)
    entity = create_entity_auto(db)
    db_folder = models.Folder(**folder.model_dump(), entity_id=entity.id)
    db.add(db_folder)
    db.commit()
    db.refresh(db_folder)

    formatted_name = f"root-tenant-{tenant_id}"
    db_folder.add_tag(
        create_tag(
            db,
            TagCreate(
                name=f"folder-{formatted_name}-tag", tenant_id=db_folder.tenant_id
            ),
        )
    )

    return db_folder


def get_root_folder(db: Session, tenant_id: int):
    root_folder = (
        db.query(models.Folder)
        .filter(
            models.Folder.name == "/",
            models.Folder.tenant_id == tenant_id,
            models.Folder.parent_id == None,
        )
        .first()
    )
    if root_folder:
        return root_folder
    else:
        return create_root_folder(db, tenant_id)


def create_folder(db: Session, folder: schemas.FolderCreate):
    # sanity check
    check_tenant_exists(db, folder.tenant_id)
    check_folder_name_taken(db, folder.name, folder.tenant_id)

    entity = create_entity_auto(db)

    root_folder = get_root_folder(db, folder.tenant_id)

    if folder.parent_id:
        check_folder_exist(db, folder_id=folder.parent_id)
    else:
        folder.parent_id = root_folder.id

    db_folder = models.Folder(**folder.model_dump(), entity_id=entity.id)
    db.add(db_folder)
    db.commit()
    db.refresh(db_folder)

    formatted_name = db_folder.tenant.name.lower().replace(" ", "-")
    formatted_name += f"-{db_folder.name.lower().replace(' ', '-')}"
    folder_tag = create_tag(
        db,
        TagCreate(name=f"folder-{formatted_name}-tag", tenant_id=db_folder.tenant_id),
    )
    db_folder.add_tag(folder_tag)
    return db_folder


def get_folder(db: Session, folder_id: int) -> models.Folder:
    db_folder = db.query(models.Folder).filter(models.Folder.id == folder_id).first()
    if db_folder is None:
        raise exceptions.FolderNotFound()
    return db_folder


def get_folders(db: Session, user_id: int) -> List[models.Folder]:
    user = get_user(db, user_id)

    if user.is_admin:
        return select(models.Folder).where(models.Folder.parent_id == None)
    else:
        if user.tenants:
            tenant_ids = user.get_tenants_ids()
            if tenant_ids:
                return (
                    select(models.Folder)
                    .where(models.Folder.tenant_id.in_(tenant_ids))
                    .where(models.Folder.parent_id == None)
                )
            # print(f"folder tree ids: {user.get_folder_tree_ids()}")
            # return db.query(models.Folder).filter(
            #     models.Folder.id.in_(user.get_folder_tree_ids())
            # )
        else:
            raise UserTenantNotAssigned()


def get_folders_from_tenant(
    db: Session, user_id: int, tenant_id: int
) -> List[models.Folder]:
    return get_folders(db, user_id).filter(models.Folder.tenant_id == tenant_id)


def get_folder_by_name(db: Session, folder_name: str):
    folder = db.query(models.Folder).filter(models.Folder.name == folder_name).first()
    if not folder:
        raise exceptions.FolderNotFound()
    return folder


def update_folder(
    db: Session,
    db_folder: schemas.Folder,
    updated_folder: schemas.FolderUpdate,
):
    # sanity checks
    values = updated_folder.model_dump(exclude_unset=True)
    folder = get_folder(db, db_folder.id)
    if updated_folder.tenant_id:
        check_tenant_exists(db, updated_folder.tenant_id)
    check_folder_name_taken(
        db, updated_folder.name, updated_folder.tenant_id, folder.id
    )

    # patch: momentarily ignoring these attributes
    # in the future, these should be treated similarly to the tags attribute.
    if updated_folder.subfolders:
        values.pop("subfolders")
    if updated_folder.devices:
        values.pop("devices")

    if updated_folder.tags:
        tags = values.pop("tags")
        tag_ids = filter_tag_ids(tags, folder.tenant_id)
        folder.entity = update_entity_tags(
            db=db,
            entity=folder.entity,
            tenant_ids=[folder.tenant_id],
            tag_ids=tag_ids,
        )

    db.execute(update(models.Folder).where(models.Folder.id == folder.id).values(values))
    db.commit()
    db.refresh(folder)
    return folder


def delete_folder(db: Session, db_folder: schemas.Folder):
    # sanity check
    check_folder_exist(db, db_folder.id)

    db.delete(db_folder)
    db.commit()
    return db_folder.id


def get_subfolders(
    db: Session, parent_folder_id: int, user_id: int
) -> List[models.Folder]:
    user = get_user(db, user_id)

    if user.is_admin:
        return db.query(models.Folder).filter(
            models.Folder.parent_id == parent_folder_id
        )
    else:
        parent_folder = get_folder(db, parent_folder_id)
        subfolders_id = [s.id for s in parent_folder.subfolders]
        return db.query(models.Folder).filter(models.Folder.id.in_(subfolders_id))


def create_subfolder(
    db: Session, parent_folder_id: int, subfolder: schemas.FolderCreate
):
    # sanity check
    parent_folder = get_folder(db, parent_folder_id)
    if not subfolder.parent_id or subfolder.parent_id != parent_folder_id:
        subfolder.parent_id = parent_folder_id
    db_folder = create_folder(db, subfolder)
    return db_folder


def update_subfolder(
    db: Session,
    parent_folder_id: int,
    db_subfolder: schemas.Folder,
    subfolder: schemas.FolderUpdate,
):
    # sanity check
    parent_folder = get_folder(db, parent_folder_id)
    if not subfolder.parent_id or subfolder.parent_id != parent_folder_id:
        raise exceptions.SubfolderParentMismatch()
    db_folder = update_folder(db, db_subfolder, subfolder)
    return db_folder


def delete_subfolder(db: Session, parent_folder_id: int, subfolder: schemas.Folder):
    # sanity check
    parent_folder = get_folder(db, parent_folder_id)
    if parent_folder.id == subfolder.parent_id:
        db_folder = delete_folder(db, subfolder)
        return db_folder
    else:
        raise exceptions.SubfolderParentMismatch()
