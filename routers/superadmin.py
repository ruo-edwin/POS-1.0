from fastapi import APIRouter, Depends, HTTPException, Form, Request, Body
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from passlib.context import CryptContext
import pytz
from pathlib import Path
from backend.db import SessionLocal
from backend.auth_utils import verify_token
from backend import models
from backend.config import templates
from pywebpush import webpush, WebPushException
import os, json


router = APIRouter(prefix="/superadmin", tags=["superadmin"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

NAIROBI_TZ = pytz.timezone("Africa/Nairobi")


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

    user = db.query(models.User).filter(
        models.User.id == token_data["user_id"]
    ).first()

    if not user or user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Only superadmin allowed")

    return user


# ----------------------------------------------------
# SUPERADMIN PANEL PAGE
# ----------------------------------------------------
@router.get("/admin_panel", response_class=HTMLResponse)
def admin_panel_page(request: Request, db: Session = Depends(get_db)):
    require_superadmin(request, db)
    return templates.TemplateResponse(
        "super_admin.html",
        {"request": request}
    )


# ----------------------------------------------------
# CREATE SUPERADMIN (RUN ONCE)
# ----------------------------------------------------
@router.post("/create_superadmin")
def create_superadmin(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    existing = db.query(models.User).filter(
        models.User.role == "superadmin"
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Superadmin already exists!"
        )

    new_superadmin = models.User(
        business_id=None,
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
# 1️⃣ GET ALL CLIENTS + SUBSCRIPTIONS + LAST LOGIN
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

        owner = db.query(models.User).filter(
            models.User.business_id == biz.id,
            models.User.role != "superadmin"
        ).first()

        if subscription:
            days_left = (subscription.end_date - datetime.utcnow()).days
        else:
            days_left = None

        # Convert last_login UTC → Nairobi time
        last_login_local = None
        if owner and owner.last_login:
            last_login_local = owner.last_login.replace(
                tzinfo=pytz.utc
            ).astimezone(NAIROBI_TZ)

        output.append({
            "business_id": biz.id,
            "business_name": biz.business_name,
            "username": owner.username if owner else None,
            "phone": biz.phone,
            "last_login": last_login_local.isoformat() if last_login_local else None,
            "subscription_status": subscription.status if subscription else "none",
            "days_left": days_left,
            "is_active": subscription.is_active if subscription else False
        })

    return output


# ----------------------------------------------------
# 2️⃣ ACTIVATE SUBSCRIPTION
# ----------------------------------------------------
@router.post("/activate/{business_id}")
def activate_subscription(
    business_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
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
def renew_subscription(
    business_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
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
def suspend_account(
    business_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
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
def reactivate_account(
    business_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
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


# ----------------------------------------------------
# 6️⃣ SEND MANUAL PUSH REMINDER
# ----------------------------------------------------

@router.post("/push_reminder/{business_id}")
def push_reminder(
    business_id: int,
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db)
):
    require_superadmin(request, db)

    title = (payload.get("title") or "").strip()
    message = (payload.get("message") or "").strip()
    if not title or not message:
        raise HTTPException(status_code=400, detail="Title and message are required")

    subs = db.query(models.PushSubscription).filter(
        models.PushSubscription.business_id == business_id
    ).all()

    if not subs:
        return {"message": "No subscribed devices for this business", "sent": 0, "failed": 0, "deleted": 0}

    # ✅ IMPORTANT: use PEM key (with BEGIN/END lines) from Railway env var
    vapid_private_pem = os.getenv("VAPID_PRIVATE_KEY_PEM")
    vapid_sub = os.getenv("VAPID_SUB", "mailto:admin@smartpos.local")

    if not vapid_private_pem:
        raise HTTPException(status_code=500, detail="VAPID_PRIVATE_KEY_PEM not set")

    # ✅ Railway-safe: write PEM to a temp file, then pass the FILE PATH to pywebpush
    pem_text = vapid_private_pem.replace("\\n", "\n").strip()
    pem_path = Path(f"/tmp/vapid_private_{business_id}.pem")
    pem_path.write_text(pem_text, encoding="utf-8")

    sent = 0
    failed = 0
    deleted = 0

    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth}
                },
                data=json.dumps({"title": title, "body": message, "url": "/"}),
                vapid_private_key=str(pem_path),  # ✅ pass file path, not PEM text
                vapid_claims={"sub": vapid_sub}
            )
            sent += 1

        except WebPushException as ex:
            failed += 1

            # ✅ Remove dead subscriptions so “sent” becomes accurate over time
            status_code = None
            try:
                if ex.response is not None:
                    status_code = ex.response.status_code
            except Exception:
                status_code = None

            if status_code in (404, 410):
                db.delete(sub)
                deleted += 1

    if deleted:
        db.commit()

    return {"message": "Reminder processed", "sent": sent, "failed": failed, "deleted": deleted}