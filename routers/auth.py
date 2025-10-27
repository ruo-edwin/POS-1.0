from fastapi import APIRouter, Depends, HTTPException, Form, HTMLResponse, Request
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from datetime import datetime
from backend.db import SessionLocal
from backend import models
from backend.main import templates

router = APIRouter(prefix="/auth", tags=["authentication"])

# 🔐 Password hashing setup
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# 📦 DB dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register_form.html", {"request": request})


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


# ✅ 1️⃣ Register a new business + admin user
@router.post("/register_form/")
def register_business(
    business_name: str = Form(...),
    username: str = Form(...),
    email: str = Form(...),
    phone: str = Form(None),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
         # ✅ Clean the password before hashing
        clean_password = password.strip()
      

        # Check if email or username already exists
        existing_business = db.query(models.Business).filter(models.Business.email == email).first()
        existing_user = db.query(models.User).filter(models.User.username == username).first()
        if existing_business:
            raise HTTPException(status_code=400, detail="Email already registered")
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already taken")

        # Create business
        new_business = models.Business(
            business_name=business_name,
            username=username,
            email=email,
            phone=phone,
            password_hash=pwd_context.hash(clean_password)
        )
        db.add(new_business)
        db.commit()
        db.refresh(new_business)

        new_business.business_code = f"RP{new_business.id}"
        db.commit()
        db.refresh(new_business)


        # Create admin user for this business
        admin_user = models.User(
            business_id=new_business.id,
            username=username,
            password_hash=pwd_context.hash(clean_password),
            role="admin",
            is_active=1,
            last_login=datetime.utcnow()
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

        return {
            "message": "✅ Business and admin user registered successfully!",
            "business_id": new_business.id,
            "business_name": new_business.business_name,
            "username": admin_user.username,
            "role": admin_user.role
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))



# ✅ 2️⃣ Login route
@router.post("/login_form/")
def login_user(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        # Check if user exists
        user = db.query(models.User).filter(models.User.username == username).first()
        if not user:
            raise HTTPException(status_code=400, detail="Invalid username or password")

        # Verify password
        if not pwd_context.verify(password, user.password_hash):
            raise HTTPException(status_code=400, detail="Invalid username or password")

        # Update last login and status
        user.is_active = 1
        user.last_login = datetime.utcnow()
        db.commit()

        # Fetch the business info
        business = db.query(models.Business).filter(models.Business.id == user.business_id).first()

        return {
            "message": f"✅ Welcome back, {user.username}!",
            "username": user.username,
            "business_name": business.business_name if business else None,
            "business_id": user.business_id,
            "role": user.role,
            "last_login": user.last_login
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    
@router.get("all_businesses/")
def get_all_businesses(db: Session = Depends(get_db)):
    businesses = db.query(models.Business).all()
    return businesses