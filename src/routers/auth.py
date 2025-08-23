from datetime import timedelta, datetime, timezone
from typing import Annotated
from ..database import SessionLocal
from fastapi import APIRouter, Depends, HTTPException, Path, status, Request
from pydantic import BaseModel
from ..models import Users
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import jwt, JWTError
from fastapi.templating import Jinja2Templates


router = APIRouter(
    prefix='/auth',
    tags=['auth']
)

SECRET_KEY = 'c376b1e1b6112627129877f30793f8b00598adb28659f1f5f8fb6614ce38540e'
ALGORITHM = 'HS256'  # algorithm used to encode the JWT token 

bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto") 
oauth2_bearer = OAuth2PasswordBearer(tokenUrl="auth/token") 
# 1.
# /auth/token is a login endpoint. After submitting your username and password, you can get the generated token returned by the backend.
#   It is not a page for viewing tokens that have not been generated or returned by the backend.
# You must submit your username and password, and only after successful verification will the server generate and return a token to you.
# So this endpoint is best understood as "get token", not "check token".
# 2.
# OAuth2PasswordBearer is a dependency. When this dependency is required by an endpoint,
#   FastAPI helps you extract the "Authorization" information (the token) from the header of the request before the endpoint function runs.
# If the dependency fails to get the token, an automatic error will be returned, and Swagger will also clearly show this as a dependency.

#refine:
# 1.
# /auth/token is an API endpoint for "obtaining a token", not a page for "viewing a token". Similar to @router.post("/token")
# The user needs to submit a username and password to this endpoint, and the backend will generate and return a token after verification.
# So more accurately, it is an API for "getting a token (login)", not a page for "viewing a token".

# 2.
# OAuth2PasswordBearer is a dependency that, before an endpoint runs,
# is used by FastAPI to automatically extract the Bearer Token from the "Authorization" field in the request header.
# If the token is missing or the format is incorrect, FastAPI will automatically return a 401 error.
# At the same time, this dependency helps Swagger UI display the authentication button, improving the usability of the API docs.

class CreateUserRequest(BaseModel):
    username: str
    email: str 
    first_name: str
    last_name: str
    password: str
    role: str 
    phone_number: str


class Token(BaseModel):
    access_token: str
    token_type: str


def get_db():
    # dependency injection
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]
# The equal sign here is not assignment, but gives a type object a variable name for reuse later, treated as a type, not a value.
# Annotated[...] is essentially a tool for combining "type + additional metadata", not limited to dependency injection scenarios.

templates = Jinja2Templates(directory="src/templates") 



### Pages ###

@router.get("/login-page")
def render_login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.get("/register-page")
def render_register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


### Endpoints ###


def authenticate_user(db, username: str, password: str):
    # db: Session is not required, Python is a dynamic language, you can omit the type
    user = db.query(Users).filter(Users.username == username).first()
    if not user:
        return False
    if not bcrypt_context.verify(password, user.hashed_password):
        return False
    return user


def create_access_token(username: str, user_id: int, role: str, expires_delta: timedelta):
    encode = {'sub':username, 'id':user_id, 'role':role}
    expires = datetime.now(timezone.utc) + expires_delta
    encode.update({'exp': expires})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)
    

async def get_current_user(token: Annotated[str, Depends(oauth2_bearer)]):      
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get('sub')
        user_id: str = payload.get('id')
        user_role: str = payload.get('role')
        if username is None or user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, 
                                detail="Could not validate user.",)
        return {'username': username, 'id': user_id, 'user_role': user_role}
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, 
                            detail="Could not validate user.",)
                                                                        


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_user(db: db_dependency, create_user_request: CreateUserRequest):
    # Annotated[...] is a type wrapper that "tells FastAPI": this parameter is of a certain type and comes from a dependency function
    # So
    # At this point, db has the Annotated type, and db_dependency comes from a dependency function,
    #   so db becomes a dependency that FastAPI will automatically inject, not a regular parameter
    create_user_model = Users(
        username=create_user_request.username,
        email=create_user_request.email,
        first_name=create_user_request.first_name,
        last_name=create_user_request.last_name,
        hashed_password=bcrypt_context.hash(create_user_request.password),
        role=create_user_request.role,
        is_active=True,
        phone_number=create_user_request.phone_number
    )

    db.add(create_user_model)
    db.commit()


@router.post("/token", status_code=status.HTTP_200_OK, response_model=Token)
async def login_for_access_token(db: db_dependency, 
                                 form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, 
                            detail="Could not validate user.",)
    token = create_access_token(user.username, user.id, user.role, timedelta(minutes=20))
    return {'access_token': token, 'token_type': 'bearer'}