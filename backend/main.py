from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from backend.db import engine, Base
import backend.models  # Ensure models are imported
from routers import auth, product, sales
from fastapi.responses import JSONResponse, RedirectResponse
from backend.auth_utils import SECRET_KEY, ALGORITHM
from jose import jwt, JWTError
app = FastAPI()

@app.middleware("http")
async def enforce_https(request: Request, call_next):
    # Check if the request came through HTTP instead of HTTPS
    proto = request.headers.get("x-forwarded-proto", "http")
    if proto == "http":
        # Redirect to HTTPS version of the same URL
        https_url = request.url.replace(scheme="https")
        return RedirectResponse(url=str(https_url))
    
    # Continue to the next middleware if already HTTPS
    return await call_next(request)

@app.middleware("http")
async def redirect_or_json_on_unauthorized(request: Request, call_next):
    # Skip auth check for public routes
    public_paths = [
        "/auth/login", "/auth/login_form", "/auth/register", "/static", "/favicon.ico"
    ]
    if any(request.url.path.startswith(p) for p in public_paths):
        return await call_next(request)

    token = request.cookies.get("access_token")

    if not token:
        # No cookie found
        if "application/json" in request.headers.get("accept", ""):
            return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
        return RedirectResponse(url="/auth/login")

    # Verify the JWT token
    try:
        jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        # Invalid or expired token
        if "application/json" in request.headers.get("accept", ""):
            return JSONResponse(status_code=401, content={"detail": "Invalid or expired token"})
        return RedirectResponse(url="/auth/login")

    # Continue request if valid
    response = await call_next(request)
    return response
# Create database tables
backend.models.Base.metadata.create_all(bind=engine)
print("✅ Tables that will be created:", Base.metadata.tables.keys())

# Allow frontend access (e.g. from local HTML files)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can restrict this later to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(product.router)
app.include_router(sales.router)
app.include_router(auth.router)

@app.get("/")
def root():
    return {"message": "✅ SmartPOS API is running"}
