from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from src.tag.schemas import Tag

class UserBase(BaseModel):  # used as common fields
    username: EmailStr
    last_login: datetime = datetime.now()
    role_id: Optional[int] = None
    disabled: Optional[bool] = False


class UserCreate(BaseModel):  # used when creating user
    username: EmailStr
    password: str

    model_config = {"extra": "forbid"}


class User(UserBase):  # used when reading user info
    id: int
    entity_id: int
    model_config = {"from_attributes": True}


class UserUpdate(UserBase):
    username: Optional[EmailStr] = None
    password: Optional[str] = None
    role_id: Optional[int] = None
    tenant_ids: Optional[List[int]] = []
    tags: Optional[List[Tag]] = []
    model_config = {"extra": "ignore"}


class UserDelete(BaseModel):
    id: int
    msg: str

