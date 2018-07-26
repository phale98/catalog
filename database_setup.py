import os
import sys
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine


Base = declarative_base()


# This was the file used to set up the database.
# It established 2 tables, Items and Categories.
class Items(Base):
    __tablename__ = 'items'
    title = Column(String(120), primary_key=True)
    categoryIds = Column(Integer, nullable=False,)
    description = Column(String(300))
    dateAdded = Column(Integer, nullable=False)
    user_id = Column(Integer, nullable=False)


class Categories(Base):
    __tablename__ = 'categories'
    categoryName = Column(String(50), nullable=False)
    id = Column(Integer, ForeignKey('items.categoryIds'), primary_key=True)
    items = relationship(Items)


class Users(Base):
    __tablename__ = 'users'
    user_name = Column(String(120), nullable=False)
    user_id = Column(Integer, ForeignKey('items.user_id'), primary_key=True)
    user_email = Column(String(120), nullable=False)
    items = relationship(Items)


engine = create_engine('sqlite:///catalogApp_2.db')
Base.metadata.create_all(engine)
