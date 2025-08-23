from .database import Base
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey


class Users(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True)
    username = Column(String, unique=True) 
    first_name = Column(String)
    last_name = Column(String) 
    hashed_password = Column(String) # encrypted password, not plain text
    is_active = Column(Boolean, default=True)
    role = Column(String) # admin role
    phone_number = Column(String, nullable=True)  # New column for phone number

class Todos(Base):
    __tablename__ = 'todos'

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(String)
    priority = Column(Integer)
    complete = Column(Boolean, default=False) 
    owner_id = Column(Integer, ForeignKey("users.id"))  # Foreign key to the user who created the todo