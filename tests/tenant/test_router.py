from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from fastapi import status

from src.tenant.constants import ErrorCode
from tests.database import (
    app,
    session,
    mock_os_data,
    mock_vendor_data,
    client_authenticated,
)


def test_read_tenants(session: Session, client_authenticated: TestClient):
    response = client_authenticated.get("/tenants/")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) == 1


def test_read_tenant(session: Session, client_authenticated: TestClient):
    response = client_authenticated.post("/tenants/", json={"name": "tenant2"})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    tenant_id = data["id"]

    response = client_authenticated.get(f"/tenants/{tenant_id}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == tenant_id
    assert data["name"] == "tenant2"
    assert len(data["folders"]) == 0


def test_read_non_existent_tenant(session: Session, client_authenticated: TestClient):
    tenant_id = 5
    response = client_authenticated.get(f"/tenants/{tenant_id}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_create_tenant(session: Session, client_authenticated: TestClient):
    response = client_authenticated.post("/tenants/", json={"name": "tenant2"})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "id" in data
    assert data["name"] == "tenant2"
    assert len(data["folders"]) == 0


def test_create_tenant_with_folder(session: Session, client_authenticated: TestClient):
    folder_id = 2
    response = client_authenticated.get(f"/folders/{folder_id}")
    folder_data = response.json()

    response = client_authenticated.post(
        "/tenants/", json={"name": "tenant2", "folders": [folder_data]}
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_create_duplicated_tenant(session: Session, client_authenticated: TestClient):
    response = client_authenticated.post(
        "/tenants/", json={"name": "tenant1"}
    )  # "tenant1" was created in session, see: tests/database.py
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == ErrorCode.TENANT_NAME_TAKEN


def test_create_incomplete_tenant(session: Session, client_authenticated: TestClient):
    # attempting to create a new tenant without a "name" value
    response = client_authenticated.post("/tenants/", json={"groups": []})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_update_tenant(session: Session, client_authenticated: TestClient):
    # Tenant with id=1 already exists in the session. See: tests/database.py
    tenant_id = 1

    # updating tenant's name
    response = client_authenticated.patch(
        f"/tenants/{tenant_id}",
        json={"name": "tenant1-updated"},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["name"] == "tenant1-updated"
    assert len(data["folders"]) == 2


def test_update_non_existent_tenant(session: Session, client_authenticated: TestClient):
    tenant_id = 5

    response = client_authenticated.patch(
        f"/tenants/{tenant_id}",
        json={"name": "tenant5-updated"},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_update_non_existent_tenant_attrs(session: Session, client_authenticated: TestClient):
    tenant_id = 1
    response = client_authenticated.patch(
        f"/tenants/{tenant_id}",
        json={
            "name": "tenant1-updated",
            "is_admin": False,  # non existing field
            "tag": "my-cool-tenant-tag",  # non existing field
        },
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_delete_tenant(session: Session, client_authenticated: TestClient):
    response = client_authenticated.post("/tenants/", json={"name": "tenant5"})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    tenant_id = data["id"]

    response = client_authenticated.delete(f"/tenants/{tenant_id}")
    assert response.status_code == status.HTTP_200_OK

    response = client_authenticated.get(f"/tenants/{tenant_id}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_non_existent_tenant(session: Session, client_authenticated: TestClient):
    tenant_id = 5
    response = client_authenticated.delete(f"/tenants/{tenant_id}")
    assert response.status_code == status.HTTP_404_NOT_FOUND
