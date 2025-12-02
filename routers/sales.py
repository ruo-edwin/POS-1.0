from fastapi import APIRouter, Depends, HTTPException, Form, Body, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from backend.db import SessionLocal
from backend import models
from backend.config import templates
from backend.auth_utils import verify_token  # ✅ import token verification

# 🔒 Secure all routes under /sales
router = APIRouter(
    prefix="/sales",
    tags=["sales"],
    dependencies=[Depends(verify_token)]  # ✅ requires valid token for all endpoints
)

@router.get("/recordsale", response_class=HTMLResponse)
async def record_sale_page(request: Request):
    return templates.TemplateResponse("record_sale.html", {"request": request})

@router.get("/salesreport", response_class=HTMLResponse)
async def sales_report_page(request: Request):
    return templates.TemplateResponse("sales_report.html", {"request": request})

# ✅ DB session dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ✅ Pydantic models for structured input
class SaleItem(BaseModel):
    product_name: str
    quantity: int

class SaleRequest(BaseModel):
    items: List[SaleItem]


# ✅ Record a sale
@router.post("/record_sale/")
def record_sale(sale_data: SaleRequest, request: Request, db: Session = Depends(get_db)):
    # ✅ Get current user from token
    
    current_user = verify_token(request)   # should return dict with business_id

    if not current_user:
        raise HTTPException(status_code=401, detail="Invalid token")

    total_sales = []

    for item in sale_data.items:
        product = db.query(models.Product).filter(models.Product.name == item.product_name).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product '{item.product_name}' not found")

        if product.quantity < item.quantity:
            raise HTTPException(status_code=400, detail=f"Not enough stock for '{item.product_name}'")

        total_price = product.price * item.quantity
        product.quantity -= item.quantity

        # ✅ Create sale record with business_id
        sale = models.Sales(
            product_id=product.id,
            quantity=item.quantity,
            total_price=total_price,
            business_id=current_user["business_id"],  # <- fix here
        )
        db.add(sale)

        total_sales.append({
            "sale_code": sale.sale_code,
            "product_name": product.name,
            "quantity_sold": item.quantity,
            "remaining_stock": product.quantity,
            "total_price": total_price
        })

    db.commit()  # commit after all sales
    # refresh all sales if needed
    return {"message": "✅ Sales recorded successfully!", "sales": total_sales}


# ✅ Get sales
@router.get("/get_sales")
def get_sales(request: Request, db: Session = Depends(get_db)):
    # ✅ Get current user from token
    current_user = verify_token(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # ✅ Only get sales for this user's business
    sales = db.query(models.Sales).filter(
        models.Sales.business_id == current_user["business_id"]
    ).all()

    result = []
    for sale in sales:
        result.append({
            "id": sale.id,
            "date": sale.created_at,
            "product_name": sale.product.name if sale.product else "Unknown",
            "quantity": sale.quantity,
            "total_price": sale.total_price,
            "buying_price": sale.product.buying_price if sale.product else None
        })
    return result
