import pytest
from typing import Union
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.database import session, mock_os_data, mock_vendor_data
from src.user.exceptions import (
    UserInvalidPassword,
    UserNotFound,
    UsernameTaken,
)
from src.user.service import (
    create_user,
    get_user,
    get_users,
    delete_user,
    update_user,
    get_devices,
    get_folders,
    assign_tenant,
)
from src.tenant.models import tenants_and_users_table
from src.user.schemas import (
    UserCreate,
    UserUpdate,
)
from src.tenant.service import get_tenants
from src.tenant.schemas import Tenant as TenantSchema
from src.auth.utils import get_user_by_username
from src.tag.models import Tag
from src.entity.exceptions import EntityTenantRelationshipMissing
from src.user.models import User

def test_create_user(session: Session) -> None:
    user = create_user(
        session,
        UserCreate(
            username="test-user-5@sia.com",
            password="_s3cr3tp@5sw0rd_",
        ),
    )
    assert user.username == "test-user-5@sia.com"


def test_create_duplicated_user(session: Session) -> None:
    with pytest.raises(UsernameTaken):
        create_user(
            session,
            UserCreate(
                username="test-user-1@sia.com",
                password="_s3cr3tp@5sw0rd_",
            ),
        )


def test_create_user_with_invalid_password(session: Session) -> None:
    with pytest.raises(UserInvalidPassword):
        create_user(
            session,
            UserCreate(
                username="test-user-5@sia.com",
                password="123",
            ),
        )


def test_create_invalid_user(session: Session) -> None:
    with pytest.raises(ValidationError):
        create_user(session, UserCreate())

    with pytest.raises(ValidationError):
        create_user(
            session,
            UserCreate(
                username="test-user-5@sia.com",
                password="1234",
                tag="my-custom-tag",
            ),
        )


def test_get_user(session: Session) -> None:
    user_id = 1  # created in tests/database.py
    user = get_user(session, user_id=user_id)
    assert user.username == "test-user-1@sia.com"
    assert user.hashed_password is not None
    assert user.id == 1


def test_get_user_with_invalid_id(session: Session) -> None:
    user_id = 5
    with pytest.raises(UserNotFound):
        get_user(session, user_id)


def test_get_user_by_username(session: Session) -> None:
    user = get_user_by_username(session, username="test-user-1@sia.com")
    assert user.username == "test-user-1@sia.com"
    assert user.hashed_password is not None
    assert user.id == 1


def test_get_user_with_invalid_username(session: Session) -> None:
    with pytest.raises(UserNotFound):
        get_user_by_username(session, username="test-user-5@sia.com")


def test_get_users(session: Session) -> None:
    # Four users were created in tests/database.py
    users = session.execute(get_users(session)).fetchall()
    assert len(users) == 4


def test_update_user(session: Session) -> None:
    user = create_user(
        session,
        UserCreate(
            username="test-user-5@sia.com",
            password="_s3cr3tp@5sw0rd_",
        ),
    )
    db_user = get_user(session, user.id)
    prev_hashed_password = db_user.hashed_password

    user = update_user(
        session,
        db_user=db_user,
        updated_user=UserUpdate(username="test-user-5-updated@sia.com"),
    )
    assert user.username == "test-user-5-updated@sia.com"
    assert user.hashed_password is not None
    assert (
        user.hashed_password == prev_hashed_password
    )  # keeping the original password unchanged
    assert user.id == db_user.id


def test_update_user_with_invalid_id(session: Session) -> None:
    db_user = get_user(session, 1)
    db_user.id = 5

    with pytest.raises(UserNotFound):
        update_user(
            session,
            db_user=db_user,
            updated_user=UserUpdate(
                username="test-user-5@sia.com", password="_s3cr3tp@5sw0rd_"
            ),
        )


def test_update_user_tags(session: Session) -> None:
    # creating a user without tenants. the update operation must fail.
    user = create_user(
        session,
        UserCreate(
            username="test-user-5@sia.com",
            password="_s3cr3tp@5sw0rd_",
        ),
    )

    tenant_id = 1
    def update_tags(user: User, tenant_id: int):
        tag_ids_tenant_1 = session.scalars(select(Tag.id).where(Tag.tenant_id == tenant_id)).all()
        user = update_user(
            session,
            db_user=user,
            updated_user=UserUpdate(tag_ids=tag_ids_tenant_1),
        )

        assert len(user.tags) == len(tag_ids_tenant_1)

    # forcing an association to tags from tenant 1
    with pytest.raises(EntityTenantRelationshipMissing):
        update_tags(user, tenant_id)

    # assigning tenant 1 to the user will solve the problem
    user = assign_tenant(session, user.id, tenant_id)
    update_tags(user, tenant_id)


def test_delete_user(session: Session) -> None:
    user = create_user(
        session,
        UserCreate(
            username="test-user-delete@sia.com",
            password="_s3cr3tp@5sw0rd_",
        ),
    )
    db_user = get_user(session, user.id)

    user_id = user.id
    deleted_user_id = delete_user(session, db_user=db_user)
    assert deleted_user_id == user_id

    with pytest.raises(UserNotFound):
        get_user(session, user.id)


def test_delete_user_with_invalid_id(session: Session) -> None:
    user = create_user(
        session,
        UserCreate(
            username="test-user-delete@sia.com",
            password="_s3cr3tp@5sw0rd_",
        ),
    )
    db_user = get_user(session, user.id)

    db_user.id = 6
    with pytest.raises(UserNotFound):
        delete_user(session, db_user=db_user)


def test_get_devices(session: Session) -> None:
    # user 1 is admin
    user_id = 1
    devices = session.execute(get_devices(session, user_id=user_id)).fetchall()
    assert len(devices) == 3

    # user 2 has 2 devices
    user_id = 2
    devices = session.execute(get_devices(session, user_id=user_id)).fetchall()
    assert len(devices) == 2

    # user 3 has 1 device
    user_id = 3
    devices = session.execute(get_devices(session, user_id=user_id)).fetchall()
    assert len(devices) == 1


def test_get_folders(session: Session) -> None:
    # user 1 is admin
    user_id = 1
    folders = session.execute(get_folders(session, user_id=user_id)).fetchall()
    assert len(folders) == 7

    # user 2 has 2 folders and 1 subfolder
    user_id = 2
    folders = session.execute(get_folders(session, user_id=user_id)).fetchall()
    assert len(folders) == 4

    # user 3 has 1 folder and 1 subfolder
    user_id = 3
    folders = session.execute(get_folders(session, user_id=user_id)).fetchall()
    assert len(folders) == 3


@pytest.mark.parametrize("user_id, n_tenants", [(1, 2), (2, 1), (3, 1)])
def test_get_tenants(session: Session, user_id: int, n_tenants) -> None:
    # user 1 is admin
    tenants = session.execute(get_tenants(session, user_id=user_id)).fetchall()
    assert len(tenants) == n_tenants


def test_assign_tenant(session: Session) -> None:
    user = create_user(
        session,
        UserCreate(
            username="test-user-5@sia.com",
            password="_s3cr3tp@5sw0rd_",
        ),
    )

    assert len(user.tenants) == 0
    tenant_id = 1
    assign_tenant(session, user.id, tenant_id)

    assert len(user.tenants) == 1


@pytest.mark.parametrize(
    argnames=[
        "user",
        "n_tenants_before_update",
        "another_user_id",
        "n_tenants_after_update",
    ],
    argvalues=[
        (
            UserCreate(
                username="test-user-5@sia.com",
                password="_s3cr3tp@5sw0rd_",
            ),
            0,
            1,
            2,
        ),
        (3, 1, 2, 2),
    ],
)
def test_update_user_multiple_tenants(
    session,
    user: Union[int, UserCreate],
    n_tenants_before_update: int,
    another_user_id: int,
    n_tenants_after_update: int,
) -> None:
    if isinstance(user, UserCreate):
        user = create_user(
            session,
            user,
        )
    else:
        user = get_user(session, user)

    assert len(user.tenants) == n_tenants_before_update

    # if its an existing user, there should be as many entries
    # as tenants it has before the update
    t_and_u_entries_query = select(tenants_and_users_table).where(
        tenants_and_users_table.c.user_id == user.id
    )
    results = session.scalars(t_and_u_entries_query).all()
    assert len(results) == n_tenants_before_update

    # lets add the tenants from another user
    another_user_tenants = session.scalars(
        get_tenants(session, user_id=another_user_id)
    ).all()
    another_user_tenants_ids = [t.id for t in another_user_tenants]

    user = update_user(
        session,
        db_user=user,
        updated_user=UserUpdate(
            tenant_ids=[*user.get_tenants_ids(), *another_user_tenants_ids]
        ),
    )

    # after the update, user.tenants has new tenant/s associated
    # and new entries have been added to the associative table.
    assert (
        len(another_user_tenants_ids) + n_tenants_before_update
        == n_tenants_after_update
    )
    assert len(user.tenants) == n_tenants_after_update
    assert len(session.scalars(t_and_u_entries_query).all()) == n_tenants_after_update
