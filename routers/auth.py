from fastapi import APIRouter, Depends, HTTPException, Form, Request
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from backend import models
from backend.db import SessionLocal
from backend.auth_utils import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, SECRET_KEY, ALGORITHM, verify_token
from backend.config import templates

router = APIRouter(prefix="/auth", tags=["authentication"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ✅ Dashboard redirect
@router.get("/dashboard")
def get_dashboard(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/auth/login")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("username")
    except JWTError:
        return RedirectResponse(url="/auth/login")

    return templates.TemplateResponse("index.html", {"request": request, "username": username})


# ✅ Registration page
@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register_form.html", {"request": request})


# ✅ Login page
@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


# ✅ Register: Business + Admin User + Subscription
@router.post("/register_form")
def register_business(
    business_name: str = Form(...),
    username: str = Form(...),
    email: str = Form(...),
    phone: str = Form(None),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        clean_password = password.strip()

        # ❌ Check if email already exists
        if db.query(models.Business).filter(models.Business.email == email).first():
            raise HTTPException(status_code=400, detail="Email already registered")

        # ❌ Check if username taken
        if db.query(models.User).filter(models.User.username == username).first():
            raise HTTPException(status_code=400, detail="Username already taken")

        # ----------------------------------------------------
        # 1️⃣ Create business
        # ----------------------------------------------------
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

        # Generate Business Code
        new_business.business_code = f"RP{new_business.id}"
        db.commit()

        # ----------------------------------------------------
        # 2️⃣ Create admin user for this business
        # ----------------------------------------------------
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

        # ----------------------------------------------------
        # 3️⃣ Create Subscription: 7-day trial
        # ----------------------------------------------------
        trial_end = datetime.utcnow() + timedelta(days=7)

        new_subscription = models.Subscription(
            business_id=new_business.id,
            status="trial",               # trial | active | expired | suspended
            start_date=datetime.utcnow(),
            end_date=trial_end,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(new_subscription)
        db.commit()

        return {"message": "✅ Business, admin user & subscription created successfully!"}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# ✅ Login and set JWT cookie + Subscription Validation (STEP 4)
@router.post("/login_form")
def login_user(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    try:
        user = db.query(models.User).filter(models.User.username == username).first()

        if not user or not pwd_context.verify(password, user.password_hash):
            raise HTTPException(status_code=400, detail="Invalid username or password")

        # 🔥 Get subscription for this business
        subscription = db.query(models.Subscription).filter(
            models.Subscription.business_id == user.business_id
        ).first()

        if not subscription:
            raise HTTPException(status_code=400, detail="Subscription record missing. Contact support.")

        now = datetime.utcnow()

        # ❌ Suspended
        if subscription.status == "suspended":
            raise HTTPException(
                status_code=403,
                detail="Your account is suspended. Please contact support."
            )

        # ❌ Trial expired
        if subscription.status == "trial" and subscription.end_date < now:
            subscription.status = "expired"
            subscription.is_active = False
            db.commit()
            raise HTTPException(
                status_code=403,
                detail="Your  7 day trial has expired. Please make payment of balance to continue.  Pochi La Biashara = 0714675719"
            )

        # ❌ Paid subscription expired
        if subscription.status == "active" and subscription.end_date < now:
            subscription.status = "expired"
            subscription.is_active = False
            db.commit()
            raise HTTPException(
                status_code=403,
                detail="Your subscription has expired. Please renew to continue."
            )

        # If all checks passed → allow login
        user.is_active = 1
        user.last_login = datetime.utcnow()
        db.commit()

        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"user_id": user.id, "username": user.username, "business_id": user.business_id, "role": user.role},
            expires_delta=access_token_expires
        )

        response = RedirectResponse(url="/auth/dashboard", status_code=302)
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        return response

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# ✅ Logout
@router.get("/logout")
def logout_user():
    response = RedirectResponse(url="https://pos-10-production.up.railway.app/auth/login")
    response.delete_cookie("access_token")
    return response
