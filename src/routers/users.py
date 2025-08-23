from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field
from ..models import Todos, Users
from ..database import SessionLocal
from typing import Annotated
from sqlalchemy.orm import Session
from .auth import get_current_user
from passlib.context import CryptContext


router = APIRouter(
    prefix='/users',
    tags=['users']
)


def get_db():
    # dependency injection
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]
bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto") 
# bcrypt_context is a class constructor call (creates an object), bcrypt_context.verify(...) is a function call


class UserVerification(BaseModel):
    password: str
    new_password: str



@router.get('/', status_code=status.HTTP_200_OK)
async def get_user(user: user_dependency, db: db_dependency):

    if user is None:
        raise HTTPException(status_code=401, detail='Authentication Failed')
    
    return db.query(Users).filter(Users.id == user.get('id')).first()


# If you want to receive multiple fields in a JSON request, it is recommended to use a Pydantic model instead of multiple Body(...)
# Because in fact, a JSON request body is a set of key-value pairs inside one {}, so it should correspond to a single receiving object (one curly brace is a whole object)
# Therefore, a Pydantic structure is a good fit for capturing a complete JSON request
# In this example, we need to receive both the new password and the old password at the same time
@router.put('/password', status_code=status.HTTP_204_NO_CONTENT)
async def change_password(user: user_dependency, db: db_dependency, user_verification: UserVerification):
    if user is None:
        raise HTTPException(status_code=401, detail='Authentication Failed')
    
    user_model = db.query(Users).filter(Users.id == user.get("id")).first()
    # In SQLAlchemy, each table in the database is mapped to a Python class
    # Each row of data is an instance object of this class, a SQLAlchemy object

    if not bcrypt_context.verify(user_verification.password, user_model.hashed_password):
        raise HTTPException(status_code=401, detail='Wrong old password')
    user_model.hashed_password = bcrypt_context.hash(user_verification.new_password)
    # encode is not encryption, it is to convert human-readable text to binary, etc., for encoding and transmission
    # hash is also not encryption, encryption can be decrypted, hash cannot be decrypted
    # The hash process is irreversible, once hashed it cannot be restored, you can only compare if the hashes are the same

    db.add(user_model)
    db.commit()
    # If this object is newly created (never saved before), add() + commit() ➜ will INSERT new data
    # If this object is queried and then modified, commit() ➜ will UPDATE the existing data
    # add() does not immediately write to the database, it just "registers this object", waiting for commit() to submit


@router.put('/phonenumber/{phone_number}', status_code=status.HTTP_204_NO_CONTENT)
async def change_phone_number(user: user_dependency, db: db_dependency, phone_number: str):
    if user is None:
        raise HTTPException(status_code=401, detail='Authentication Failed')
    user_model=db.query(Users).filter(Users.id == user.get('id')).first()
    user_model.phone_number = phone_number
    db.add(user_model)
    db.commit()