from fastapi import APIRouter, Depends, HTTPException, Form, Request
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from passlib.context import CryptContext

from backend.db import SessionLocal
from backend.auth_utils import verify_token
from backend import models
from backend.config import templates


router = APIRouter(prefix="/superadmin", tags=["superadmin"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ----------------------------------------------------
# DB Session
# ----------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ----------------------------------------------------
# SUPERADMIN AUTH CHECK
# ----------------------------------------------------
def require_superadmin(request: Request, db: Session):
    token_data = verify_token(request)
    if not token_data:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = db.query(models.User).filter(models.User.id == token_data["user_id"]).first()
    if not user or user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Only superadmin allowed")

    return user


# ----------------------------------------------------
# SUPERADMIN PANEL PAGE
# ----------------------------------------------------
@router.get("/admin_panel", response_class=HTMLResponse)
def admin_panel_page(request: Request, db: Session = Depends(get_db)):
    require_superadmin(request, db)
    return templates.TemplateResponse("admin_dashboard.html", {"request": request})


# ----------------------------------------------------
# CREATE SUPERADMIN (RUN ONCE)
# ----------------------------------------------------
@router.post("/create_superadmin")
def create_superadmin(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    existing = db.query(models.User).filter(models.User.role == "superadmin").first()
    if existing:
        raise HTTPException(status_code=400, detail="Superadmin already exists!")

    new_superadmin = models.User(
        business_id=0,      # Superadmin is not tied to a business
        username=username,
        password_hash=pwd_context.hash(password),
        role="superadmin",
        is_active=1,
         last_login=datetime.utcnow()
    )

    db.add(new_superadmin)
    db.commit()

    return {"message": "🔥 Superadmin created successfully!"}


# ----------------------------------------------------
# 1️⃣ GET ALL CLIENTS + SUBSCRIPTIONS
# ----------------------------------------------------
@router.get("/get_all_clients")
def get_all_clients(request: Request, db: Session = Depends(get_db)):
    require_superadmin(request, db)

    businesses = db.query(models.Business).all()
    output = []

    for biz in businesses:
        subscription = db.query(models.Subscription).filter(
            models.Subscription.business_id == biz.id
        ).first()

        if subscription:
            days_left = (subscription.end_date - datetime.utcnow()).days
        else:
            days_left = None

        output.append({
            "business_id": biz.id,
            "business_name": biz.business_name,
            "username": biz.username,
            "phone": biz.phone,
            "subscription_status": subscription.status if subscription else "none",
            "days_left": days_left,
            "is_active": subscription.is_active if subscription else False
        })

    return output


# ----------------------------------------------------
# 2️⃣ ACTIVATE SUBSCRIPTION (After Trial or Expired)
# ----------------------------------------------------
@router.post("/activate/{business_id}")
def activate_subscription(business_id: int, request: Request, db: Session = Depends(get_db)):
    require_superadmin(request, db)

    subscription = db.query(models.Subscription).filter(
        models.Subscription.business_id == business_id
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    subscription.status = "active"
    subscription.is_active = True
    subscription.start_date = datetime.utcnow()
    subscription.end_date = datetime.utcnow() + timedelta(days=30)
    subscription.updated_at = datetime.utcnow()

    db.commit()
    return {"message": "Subscription activated for 30 days"}


# ----------------------------------------------------
# 3️⃣ RENEW +30 DAYS
# ----------------------------------------------------
@router.post("/renew/{business_id}")
def renew_subscription(business_id: int, request: Request, db: Session = Depends(get_db)):
    require_superadmin(request, db)

    subscription = db.query(models.Subscription).filter(
        models.Subscription.business_id == business_id
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    subscription.status = "active"
    subscription.is_active = True
    subscription.end_date += timedelta(days=30)
    subscription.updated_at = datetime.utcnow()

    db.commit()
    return {"message": "Subscription renewed +30 days"}


# ----------------------------------------------------
# 4️⃣ SUSPEND BUSINESS
# ----------------------------------------------------
@router.post("/suspend/{business_id}")
def suspend_account(business_id: int, request: Request, db: Session = Depends(get_db)):
    require_superadmin(request, db)

    subscription = db.query(models.Subscription).filter(
        models.Subscription.business_id == business_id
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    subscription.status = "suspended"
    subscription.is_active = False
    subscription.updated_at = datetime.utcnow()

    db.commit()
    return {"message": "Business suspended"}


# ----------------------------------------------------
# 5️⃣ REACTIVATE BUSINESS
# ----------------------------------------------------
@router.post("/reactivate/{business_id}")
def reactivate_account(business_id: int, request: Request, db: Session = Depends(get_db)):
    require_superadmin(request, db)

    subscription = db.query(models.Subscription).filter(
        models.Subscription.business_id == business_id
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    subscription.status = "active"
    subscription.is_active = True
    subscription.updated_at = datetime.utcnow()

    db.commit()
    return {"message": "Business reactivated"}
