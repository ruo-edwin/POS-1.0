from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.db import engine, Base
import backend.models  # Ensure models are imported
from routers import auth, product, sales



app = FastAPI()


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
