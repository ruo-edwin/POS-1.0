from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from dotenv import load_dotenv
import os

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
print("DEBUG: DATABASE_URL =", DATABASE_URL)

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is missing or not set.")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,   # Reconnects automatically if MySQL has gone away
    pool_recycle=280,     # Recycle connections every ~5 min
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()