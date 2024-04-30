import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session
from src.tenant.exceptions import TenantNotFound
from tests.database import session, mock_os_data, mock_vendor_data

from src.folder.exceptions import (
    FolderNameTaken,
    FolderNotFound,
)
from src.folder.service import (
    create_folder,
    get_folder,
    get_folder_by_name,
    get_folders,
    delete_folder,
    update_folder,
)
from src.folder.schemas import (
    FolderCreate,
    FolderUpdate,
)
from src.user.service import create_user
from src.user.schemas import UserCreate
from src.user.exceptions import UserTenantNotAssigned


def test_create_folder(session: Session) -> None:
    folder = create_folder(session, FolderCreate(name="folder5", tenant_id=1))
    assert folder.name == "folder5"
    assert folder.tenant_id == 1
    assert len(folder.tags) == 1


def test_create_duplicated_folder(session: Session) -> None:
    with pytest.raises(FolderNameTaken):
        create_folder(session, FolderCreate(name="folder1", tenant_id=1))


def test_create_incomplete_folder(session: Session) -> None:
    with pytest.raises(ValidationError):
        create_folder(session, FolderCreate())


def test_create_folder_with_invalid_tenant(session: Session) -> None:
    with pytest.raises(TenantNotFound):
        create_folder(session, FolderCreate(name="folder5", tenant_id=5))


def test_get_folder(session: Session) -> None:
    folder = get_folder(session, folder_id=3)
    assert folder.name == "folder1"
    assert folder.tenant_id == 1
    assert len(folder.tags) == 2
    assert folder.tags[0].name == "folder-tenant1-folder1-tag"


def test_get_folder_with_invalid_id(session: Session) -> None:
    with pytest.raises(FolderNotFound):
        get_folder(session, folder_id=16)


def test_get_folder_by_name(session: Session) -> None:
    folder = get_folder_by_name(session, folder_name="folder1")
    assert folder.name == "folder1"
    assert folder.tenant_id == 1


def test_get_folder_with_invalid_name(session: Session) -> None:
    with pytest.raises(FolderNotFound):
        get_folder_by_name(session, folder_name="folder5")


def test_get_folders(session: Session) -> None:
    # five folders/subfolders were created in tests/database.py
    # pagination results only counts "/" folders as items as the others count as subfolders of them.
    folders = session.execute(get_folders(session, user_id=1)).fetchall()
    assert len(folders) == 2

    folders = session.execute(get_folders(session, user_id=2)).fetchall()
    assert len(folders) == 1

    folders = session.execute(get_folders(session, user_id=3)).fetchall()
    assert len(folders) == 1

    folders = session.execute(get_folders(session, user_id=4)).fetchall()
    assert len(folders) == 1

    user5 = create_user(
        session,
        UserCreate(
            email="test-user-5@sia.com",
            username="test-user-5",
            password="_s3cr3tp@5sw0rd_",
        ),
    )
    with pytest.raises(UserTenantNotAssigned):
        folders = session.execute(get_folders(
            session, user_id=5
        )).fetchall()  # this user has no tenant asigned so it will raise an exception


def test_update_folder(session: Session) -> None:
    folder = create_folder(session, FolderCreate(name="folder5", tenant_id=1))
    db_folder = get_folder(session, folder.id)

    folder = update_folder(
        session,
        db_folder=db_folder,
        updated_folder=FolderUpdate(name="folder-custom"),
    )
    assert folder.name == "folder-custom"
    assert folder.tenant_id == 1


def test_update_folder_with_invalid_tenant(session: Session) -> None:
    folder = create_folder(session, FolderCreate(name="folder5", tenant_id=1))
    db_folder = get_folder(session, folder.id)

    with pytest.raises(TenantNotFound):
        folder = update_folder(
            session,
            db_folder=db_folder,
            updated_folder=FolderUpdate(name="folder-custom", tenant_id=5),
        )


def test_update_folder_with_invalid_id(session: Session) -> None:
    db_folder = get_folder(session, 1)
    db_folder.id = 16

    with pytest.raises(FolderNotFound):
        update_folder(
            session,
            db_folder=db_folder,
            updated_folder=FolderUpdate(name="folder-custom", tenant_id=1),
        )


def test_delete_folder(session: Session) -> None:
    folder = create_folder(session, FolderCreate(name="folder6delete", tenant_id=1))
    db_folder = get_folder(session, folder.id)

    folder_id = folder.id
    deleted_folder_id = delete_folder(session, db_folder=db_folder)
    assert deleted_folder_id == folder_id

    with pytest.raises(FolderNotFound):
        get_folder(session, folder.id)


def test_delete_folder_with_invalid_id(session: Session) -> None:
    db_folder = get_folder(session, 5)

    db_folder.id = 16  # this id must not exist
    with pytest.raises(FolderNotFound):
        delete_folder(session, db_folder=db_folder)
