import os
import datetime
from fastapi import Depends
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import Any, Optional, Dict
from jose import JWTError, jwt
from passlib.context import CryptContext
from src.database import get_db
from src.user import models, schemas
from src.user import exceptions as user_exceptions
from src.auth import exceptions

load_dotenv()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def get_user_by_username(db: Session, username: str) -> models.User:
    #user = db.query(models.User).filter(models.User.username == username).first()
    user = db.scalars(select(models.User).where(models.User.username == username)).first()
    if not user:
        raise user_exceptions.UserNotFound()
    return user


def authenticate_user(username: str, password: str, db: Session = Depends(get_db)):
    user = get_user_by_username(db, username)
    if not verify_password(password, user.hashed_password):
        raise exceptions.IncorrectUserOrPassword()
    return user


def encode_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.now(datetime.UTC) + expires_delta
    else:
        expire = datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, os.getenv("SECRET_KEY"), algorithm=os.getenv("ALGORITHM")
    )
    return encoded_jwt


def create_access_token(
    user: models.User,
    expiration_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")),
):
    serialized_user = schemas.User.model_validate(user).model_dump_json()
    access_token_expires = datetime.timedelta(minutes=expiration_minutes)
    access_token = encode_access_token(
        data={"sub": serialized_user}, expires_delta=access_token_expires
    )
    return access_token


def get_refresh_token_settings(
    refresh_token: str,
    expired: bool = False,
) -> Dict[str, Any]:
    base_cookie = {
        "key": os.getenv("REFRESH_SECRET_KEY"),
        "httponly": True,
        "samesite": "none",
        "secure": os.getenv("SECURE_COOKIES"),
        "domain": os.getenv("SITE_DOMAIN"),
    }
    if expired:
        return base_cookie

    return {
        **base_cookie,
        "value": refresh_token,
        "max_age": int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS")),
    }
