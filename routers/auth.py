from fastapi import APIRouter, Depends, HTTPException, Form, Request
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from backend import models
from backend.db import SessionLocal
from backend.auth_utils import (
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    SECRET_KEY,
    ALGORITHM,
    verify_token
)
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
def get_dashboard(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/auth/login")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
    except JWTError:
        return RedirectResponse(url="/auth/login")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return RedirectResponse(url="/auth/login")

    # 🔥 NEW: Staff cannot access dashboard
    if user.role == "staff":
        return RedirectResponse(url="/sales/recordsale")

    business_name = user.business.business_name if user.business_id else "Superadmin"

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "username": user.username,
            "business_name": business_name,
            "last_login": user.last_login,
            "role": user.role
        }
    )


# ✅ Registration page
@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register_form.html", {"request": request})


# ✅ Login page
@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# ✅ manage staff page
@router.get("/manage_staff", response_class=HTMLResponse)
def manage_staff_page(
    request: Request,
    current_user: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    # 🔒 Admin only
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    business_id = current_user["business_id"]

    staff_list = db.query(models.User).filter(
        models.User.business_id == business_id,
        models.User.role.in_(["staff", "manager"])
    ).all()

    return templates.TemplateResponse(
        "manage_staff.html",
        {
            "request": request,
            "staff_list": staff_list
        }
    )

# ✅ Register: Business + Admin + Subscription + AUTO LOGIN
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

        if db.query(models.Business).filter(models.Business.email == email).first():
            raise HTTPException(status_code=400, detail="Email already registered")

        if db.query(models.User).filter(models.User.username == username).first():
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

        # Create admin user
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

        # Create trial subscription
        trial_end = datetime.utcnow() + timedelta(days=7)
        new_subscription = models.Subscription(
            business_id=new_business.id,
            status="trial",
            start_date=datetime.utcnow(),
            end_date=trial_end,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(new_subscription)
        db.commit()

        # AUTO LOGIN TOKEN
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={
                "user_id": admin_user.id,
                "username": admin_user.username,
                "business_id": admin_user.business_id,
                "role": admin_user.role
            },
            expires_delta=access_token_expires
        )

        response = JSONResponse(content={
            "message": "✅ Account created successfully! Redirecting to dashboard...",
            "redirect": "/auth/dashboard?new=1"
        })

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


# ✅ Login + Subscription Validation + SUPERADMIN BYPASS
@router.post("/login_form")
def login_user(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    try:
        user = db.query(models.User).filter(models.User.username == username).first()

        if not user or not pwd_context.verify(password, user.password_hash):
            raise HTTPException(status_code=400, detail="Invalid username or password")

        # SUPERADMIN BYPASS
        if user.role == "superadmin":
            user.is_active = 1
            user.last_login = datetime.utcnow()
            db.commit()

            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={
                    "user_id": user.id,
                    "username": user.username,
                    "business_id": user.business_id,
                    "role": user.role
                },
                expires_delta=access_token_expires
            )

            response = RedirectResponse(url="/superadmin/admin_panel", status_code=302)
            response.set_cookie(
                key="access_token",
                value=access_token,
                httponly=True,
                secure=True,
                samesite="lax",
                max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
            )
            return response

        subscription = db.query(models.Subscription).filter(
            models.Subscription.business_id == user.business_id
        ).first()

        if not subscription:
            raise HTTPException(status_code=400, detail="Subscription record missing. Contact support.")

        now = datetime.utcnow()

        if subscription.status == "suspended":
            raise HTTPException(status_code=403, detail="Your account is suspended.")

        if subscription.status == "trial" and subscription.end_date < now:
            subscription.status = "expired"
            subscription.is_active = False
            db.commit()
            raise HTTPException(status_code=403, detail="Your trial has expired.")

        if subscription.status == "active" and subscription.end_date < now:
            subscription.status = "expired"
            subscription.is_active = False
            db.commit()
            raise HTTPException(status_code=403, detail="Your subscription has expired.")

        user.is_active = 1
        user.last_login = datetime.utcnow()
        db.commit()

        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={
                "user_id": user.id,
                "username": user.username,
                "business_id": user.business_id,
                "role": user.role
            },
            expires_delta=access_token_expires
        )

        # 🔥 NEW: Role-based redirect
        if user.role == "staff":
            redirect_url = "/sales/recordsale"
        elif user.role == "manager":
            redirect_url = "/auth/dashboard"
        else:  # admin
            redirect_url = "/auth/dashboard"

        response = RedirectResponse(url=redirect_url, status_code=302)

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
@router.post("/create_staff")
def create_staff(
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    current_user: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    # 🔒 Admin only
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    if role not in ["staff", "manager"]:
        raise HTTPException(status_code=400, detail="Invalid role selected")

    # Prevent duplicate username
    existing = db.query(models.User).filter(models.User.username == username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    new_user = models.User(
        business_id=current_user["business_id"],
        username=username,
        password_hash=pwd_context.hash(password.strip()),
        role=role,
        is_active=1
    )

    db.add(new_user)
    db.commit()

    return RedirectResponse(url="/auth/manage_staff", status_code=303)

# ✅ Logout
@router.get("/logout")
def logout_user():
    response = RedirectResponse(url="/auth/login")
    response.delete_cookie("access_token")
    return response