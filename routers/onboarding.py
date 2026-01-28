from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session

from backend.db import SessionLocal
from backend import models
from backend.auth_utils import verify_token

router = APIRouter(prefix="/onboarding", tags=["onboarding"], dependencies=[Depends(verify_token)])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/status")
def onboarding_status(
    request: Request,
    current_user: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    business_id = current_user.get("business_id")
    if not business_id:
        raise HTTPException(status_code=400, detail="No business_id in token")

    # -----------------------------
    # Reality checks (DB truth)
    # -----------------------------
    has_product = db.query(models.Product).filter(
        models.Product.business_id == business_id
    ).first() is not None

    has_sale = db.query(models.Order).filter(
        models.Order.business_id == business_id
    ).first() is not None

    # -----------------------------
    # Event checks (onboarding logs)
    # -----------------------------
    viewed_stock = db.query(models.OnboardingEvent).filter(
        models.OnboardingEvent.business_id == business_id,
        models.OnboardingEvent.event == "view_stock"
    ).first() is not None

    viewed_report = db.query(models.OnboardingEvent).filter(
        models.OnboardingEvent.business_id == business_id,
        models.OnboardingEvent.event == "view_report"
    ).first() is not None

    # ✅ Fallback logic for old users:
    # If they already have products, treat stock as "done"
    # If they already have sales/orders, treat report as "done"
    steps = {
        "add_product": has_product,
        "update_stock": viewed_stock or has_product,
        "sell_product": has_sale,
        "view_report": viewed_report or has_sale
    }

    completed = sum(1 for v in steps.values() if v)
    progress = int((completed / 4) * 100)

    return {"steps": steps, "progress": progress}
