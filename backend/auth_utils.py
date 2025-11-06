from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
from jose import jwt , JWTError
from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from starlette.status import HTTP_401_UNAUTHORIZED
load_dotenv()


SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is missing or not set.")



token_blacklist = set()  # In-memory token blacklist for simplicity

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def blacklist_token(token: str):
    token_blacklist.add(token)

def verify_token(request: Request):
    token = request.cookies.get("access_token")
    
    if not token or token in token_blacklist:
        # If the request is from an API (fetch), raise HTTP 401 instead of redirect
        if request.url.path.startswith("/api") or request.headers.get("accept") == "application/json":
            raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        # Otherwise, it's a web page — redirect to login
        return RedirectResponse(url="https://pos-10-production.up.railway.app/auth/login")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        if request.url.path.startswith("/api") or request.headers.get("accept") == "application/json":
            raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
        return RedirectResponse(url="https://pos-10-production.up.railway.app/auth/login")