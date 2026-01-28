from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

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

    # Step 1: at least 1 product
    has_product = db.query(models.Product).filter(models.Product.business_id == business_id).first() is not None

    # Step 2: stock page opened at least once
    viewed_stock = db.query(models.OnboardingEvent).filter(
        models.OnboardingEvent.business_id == business_id,
        models.OnboardingEvent.event == "view_stock"
    ).first() is not None

    # Step 3: at least 1 order (meaning a sale happened)
    has_sale = db.query(models.Order).filter(models.Order.business_id == business_id).first() is not None

    # Step 4: report page opened at least once
    viewed_report = db.query(models.OnboardingEvent).filter(
        models.OnboardingEvent.business_id == business_id,
        models.OnboardingEvent.event == "view_report"
    ).first() is not None

    steps = {
        "add_product": has_product,
        "update_stock": viewed_stock,
        "sell_product": has_sale,
        "view_report": viewed_report
    }

    completed = sum(1 for v in steps.values() if v)
    progress = int((completed / 4) * 100)

    return {"steps": steps, "progress": progress}
