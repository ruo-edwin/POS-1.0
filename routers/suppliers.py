from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from backend.db import SessionLocal
from backend import models
from backend.config import templates
from backend.auth_utils import verify_token

router = APIRouter(
    prefix="/suppliers",
    tags=["suppliers"],
    dependencies=[Depends(verify_token)]
)

# -------------------------
# DB Session
# -------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/", response_class=HTMLResponse)
def suppliers_page(request: Request):

    return templates.TemplateResponse(
        "suppliers.html",
        {
            "request": request,
            "active_page": "suppliers"
        }
    )

@router.post("/add")
def add_supplier(
    request: Request,
    name: str,
    phone: str = None,
    email: str = None,
    db: Session = Depends(get_db)
):

    user = verify_token(request)

    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    supplier = models.Supplier(
        name=name,
        phone=phone,
        email=email,
        business_id=user["business_id"]
    )

    db.add(supplier)
    db.commit()

    return {"message": "Supplier added successfully"}

@router.get("/list")
def get_suppliers(request: Request, db: Session = Depends(get_db)):

    user = verify_token(request)

    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    suppliers = db.query(models.Supplier).filter(
        models.Supplier.business_id == user["business_id"]
    ).all()

    return suppliers