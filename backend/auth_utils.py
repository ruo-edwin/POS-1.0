from fastapi.security import OAuth2PasswordBearer
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
from jose import jwt , JWTError
from fastapi import Depends, HTTPException

load_dotenv()


SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is missing or not set.")


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

token_blacklist = set()  # In-memory token blacklist for simplicity

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def blacklist_token(token: str):
    token_blacklist.add(token)

def verify_token(token: str = Depends(oauth2_scheme)):
    if token in token_blacklist:
        raise HTTPException(status_code=401, detail="Token revoked. Please log in again.")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
