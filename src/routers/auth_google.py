from fastapi import APIRouter, Request
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
from fastapi.responses import RedirectResponse
from datetime import timedelta
import os
import traceback

from src.models import Users
from src.database import SessionLocal
from src.routers.auth import create_access_token

router = APIRouter()

# OAuth settings
config = Config(environ=os.environ)
oauth = OAuth(config)

oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

@router.get("/auth/login")
async def login(request: Request):
    base_url = str(request.base_url)
    if base_url.startswith("http://localhost") or base_url.startswith("http://127.0.0.1"):
        redirect_uri = "http://localhost:8000/auth/callback"
    else:
        redirect_uri = "https://todo-list-app-yeui.onrender.com/auth/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/auth/callback")
async def auth_callback(request: Request):
    try:
        print("🔄 Received Google callback")

        token = await oauth.google.authorize_access_token(request)
        # Only keep the most critical print for debugging
        print("✅ Got user info:", token.get("userinfo", {}).get("email"), "|", token.get("userinfo", {}).get("name"))

        # Try to get userinfo or fallback to id_token
        user_info = token.get("userinfo")
        if not user_info:
            user_info = await oauth.google.parse_id_token(request, token)

        email = user_info["email"]
        username = email.split("@")[0]
        first_name = user_info.get("given_name", "")
        last_name = user_info.get("family_name", "")

        db = SessionLocal()
        db_user = db.query(Users).filter(Users.email == email).first()

        if not db_user:
            db_user = Users(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                hashed_password="",  # OAuth user has no password
                role="user",
                is_active=True,
                phone_number=""
            )
            db.add(db_user)
            db.commit()
            db.refresh(db_user)

        jwt_token = create_access_token(
            username=db_user.username,
            user_id=db_user.id,
            role=db_user.role,
            expires_delta=timedelta(minutes=20)
        )

        response = RedirectResponse(url="/todos/todo-page")
        # httponly=True is for backend only, frontend cannot read it. Since cookies are automatically included in every API request, the backend can get cookie info from the request.
        # response.set_cookie(key="access_token", value=jwt_token, httponly=True) 
        response.set_cookie(key="access_token", value=jwt_token, httponly=False)  # Allow JS to read
        return response

    except Exception as e:
        print("❌ Error in auth_callback:", e)
        traceback.print_exc()
        return RedirectResponse(url="/auth/login-page")  # Fallback to login page

@router.get("/auth/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/auth/login-page")
    response.delete_cookie("access_token")
    return response
