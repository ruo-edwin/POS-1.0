import os
from fastapi import APIRouter, Depends, HTTPException, Request, Body
from sqlalchemy.orm import Session

from backend.db import SessionLocal
from backend.auth_utils import verify_token
from backend import models

router = APIRouter(prefix="/push", tags=["push"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def b64_to_b64url(s: str) -> str:
    """
    Convert standard base64 to base64url (no padding).
    Browser Push API expects base64url for the applicationServerKey conversion.
    """
    return s.replace("+", "-").replace("/", "_").rstrip("=")


@router.get("/vapid_public_key")
def vapid_public_key():
    public_key = os.getenv("VAPID_PUBLIC_KEY")
    if not public_key:
        raise HTTPException(status_code=500, detail="VAPID_PUBLIC_KEY not set")

    # ✅ FIX: return base64url (no = padding) so atob() doesn't throw InvalidCharacterError
    public_key = public_key.strip()
    return {"publicKey": b64_to_b64url(public_key)}


@router.post("/subscribe")
def subscribe(request: Request, payload: dict = Body(...), db: Session = Depends(get_db)):
    token_data = verify_token(request)
    if not token_data:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = db.query(models.User).filter(models.User.id == token_data["user_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.business_id:
        raise HTTPException(status_code=400, detail="User has no business_id (cannot subscribe)")

    endpoint = payload.get("endpoint")
    keys = payload.get("keys") or {}
    p256dh = keys.get("p256dh")
    auth = keys.get("auth")

    if not endpoint or not p256dh or not auth:
        raise HTTPException(status_code=400, detail="Invalid subscription payload")

    # ✅ UPSERT by endpoint (same device updates instead of getting stuck)
    existing = db.query(models.PushSubscription).filter(
        models.PushSubscription.endpoint == endpoint
    ).first()

    if existing:
        existing.user_id = user.id
        existing.business_id = user.business_id
        existing.p256dh = p256dh
        existing.auth = auth
        db.commit()
        return {"message": "Updated subscription"}

    sub = models.PushSubscription(
        user_id=user.id,
        business_id=user.business_id,
        endpoint=endpoint,
        p256dh=p256dh,
        auth=auth
    )

    db.add(sub)
    db.commit()
    return {"message": "Subscribed"}
