from fastapi import APIRouter, Depends, HTTPException, Path, status, Request
from pydantic import BaseModel, Field
from ..models import Todos, Users
from ..database import SessionLocal
from typing import Annotated
from sqlalchemy.orm import Session
from .auth import get_current_user
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from .todos import TodoRequest


templates = Jinja2Templates(directory="src/templates")


router = APIRouter(
    prefix='/admin',
    tags=['admin']
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


#### Pages ###

@router.get("/dashboard")
async def admin_dashboard(request: Request, db: db_dependency):
    try:
        token = request.cookies.get('access_token')
        if token is None:
            raise HTTPException(status_code=401, detail="No token provided")

        from .auth import get_current_user
        user = await get_current_user(token)
        if user.get("user_role") != "admin":
            raise HTTPException(status_code=403, detail="Access denied")

        students = db.query(Users).filter(Users.role != "admin").all()
        return templates.TemplateResponse("admin_dashboard.html", {
            "request": request,
            "students": students,
            "user": user  # satisfies the navbar condition
        })

    except:
        from .todos import redirect_to_login
        return redirect_to_login()


@router.get("/user/{user_id}/todos-page")
async def view_student_todos(request: Request, user_id: int, db: db_dependency):
    try:
        # Get token from cookie and verify if user is admin
        token = request.cookies.get('access_token')
        from .auth import get_current_user
        current_user = await get_current_user(token)

        if current_user.get("user_role") != "admin":
            raise HTTPException(status_code=403, detail="Access denied")

        # Query target student's todos
        todos = db.query(Todos).filter(Todos.owner_id == user_id).all()
        student = db.query(Users).filter(Users.id == user_id).first()

        return templates.TemplateResponse("todo.html", {
            "request": request,
            "todos": todos,
            "user": current_user,
            "viewed_student": student.username,
            "is_teacher_view": True
        })
    except:
        from .todos import redirect_to_login
        return redirect_to_login()


@router.get("/user/{student_id}/add-todo-page")
async def render_add_todo_for_student(request: Request, student_id: int, db: db_dependency):
    token = request.cookies.get('access_token')
    from .auth import get_current_user
    user = await get_current_user(token)

    if user.get("user_role") != "admin":
        raise HTTPException(status_code=403)

    return templates.TemplateResponse("add-todo.html", {
        "request": request,
        "user": user,
        "is_teacher_view": True,
        "student_id": student_id
    })


@router.get("/user/{student_id}/edit-todo-page/{todo_id}")
async def render_edit_todo_for_student(request: Request, student_id: int, todo_id: int, db: db_dependency):
    token = request.cookies.get('access_token')
    from .auth import get_current_user
    user = await get_current_user(token)

    if user.get("user_role") != "admin":
        raise HTTPException(status_code=403)

    todo = db.query(Todos).filter(Todos.id == todo_id, Todos.owner_id == student_id).first()
    if not todo:
        raise HTTPException(status_code=404)

    return templates.TemplateResponse("edit-todo.html", {
        "request": request,
        "user": user,
        "todo": todo,
        "is_teacher_view": True,
        "student_id": student_id
    })


### Endpoints ###

@router.get('/', status_code=status.HTTP_200_OK)
async def read_all_todos(db: db_dependency, user: user_dependency):
    
    if user is None or user.get('user_role') != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    return db.query(Todos).all()


@router.get("/users", status_code=status.HTTP_200_OK)
async def read_all_users(db: db_dependency, user: user_dependency):

    if user is None or user.get('user_role') != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    return db.query(Users).all()
    # The essence of JWT: the server/database does not store the token, each request only needs to verify the token itself, no need to check with the database
    # However, the server still needs to store basic user info to create the token at first login, but afterwards, user info in the database is not needed for verification
    # Because JWT login only verifies the JWT itself, not the database, so it is stateless -- the server does not save any login state or info
    # Therefore, if someone else gets the token, they can also verify successfully; if the user's role in the database changes, the token can still access with the previous role


@router.delete('/todos/{todo_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_todo(db: db_dependency, user: user_dependency, todo_id: int = Path(gt=0)):

    if user is None or user.get('user_role') != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    todo_model = db.query(Todos).filter(Todos.id == todo_id).first()
    if todo_model is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Todo not found")
    
    db.query(Todos).filter(Todos.id == todo_id).delete()
    # db.delete(todo_model) is also possible, but not creating a new one in update and putting it back
    # todo_model.delete() is not available, because ORM instances themselves do not have a delete() method.
    # The instance is like a book taken out, it cannot delete itself from the database, it must be deleted by db.delete(...) through the session manager.

    db.commit()


@router.post("/user/{user_id}/todo", status_code=status.HTTP_201_CREATED)
async def create_todo_for_student(user_id: int, db: db_dependency, request: Request, todo: TodoRequest):
    token = request.cookies.get('access_token')
    current_user = await get_current_user(token)
    if current_user.get("user_role") != "admin":
        raise HTTPException(status_code=403, detail="Only teachers can do this.")

    todo_model = Todos(**todo.dict(), owner_id=user_id)
    db.add(todo_model)
    db.commit()


@router.put("/user/{user_id}/todo/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_todo_for_student(user_id: int, todo_id: int, db: db_dependency, request: Request, todo: TodoRequest):
    token = request.cookies.get('access_token')
    current_user = await get_current_user(token)
    if current_user.get("user_role") != "admin":
        raise HTTPException(status_code=403)

    todo_model = db.query(Todos).filter(Todos.id == todo_id, Todos.owner_id == user_id).first()
    if not todo_model:
        raise HTTPException(status_code=404)

    todo_model.title = todo.title
    todo_model.description = todo.description
    todo_model.priority = todo.priority
    todo_model.complete = todo.complete
    db.commit()


@router.delete("/user/{user_id}/todo/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_todo_for_student(user_id: int, todo_id: int, db: db_dependency, request: Request):
    token = request.cookies.get('access_token')
    current_user = await get_current_user(token)
    if current_user.get("user_role") != "admin":
        raise HTTPException(status_code=403)

    db.query(Todos).filter(Todos.id == todo_id, Todos.owner_id == user_id).delete()
    db.commit()
