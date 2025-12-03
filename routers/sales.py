from fastapi import APIRouter, Depends, HTTPException, Form, Body, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import List
from backend.db import SessionLocal
from backend import models
from backend.config import templates
from backend.auth_utils import verify_token  # secure routes


router = APIRouter(
    prefix="/sales",
    tags=["sales"],
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


# -------------------------
# Pages
# -------------------------
@router.get("/recordsale", response_class=HTMLResponse)
async def record_sale_page(request: Request):
    return templates.TemplateResponse("record_sale.html", {"request": request})


@router.get("/salesreport", response_class=HTMLResponse)
async def sales_report_page(request: Request):
    return templates.TemplateResponse("sales_report.html", {"request": request})


# -------------------------
# Pydantic Models
# -------------------------
class SaleItem(BaseModel):
    product_name: str
    quantity: int


class SaleRequest(BaseModel):
    items: List[SaleItem]


# ======================================================
# 🚀 RECORD SALE — ONE ORDER = ONE sale_code
# ======================================================
@router.post("/record_sale/")
def record_sale(sale_data: SaleRequest, request: Request, db: Session = Depends(get_db)):

    current_user = verify_token(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Invalid token")

    business_id = current_user["business_id"]

    # =====================================================
    # SAFE ORDER CODE GENERATION (NO DUPLICATES EVER)
    # =====================================================
    result = db.execute(text("""
        SELECT sale_code FROM sales 
        ORDER BY id DESC LIMIT 1
    """)).fetchone()

    if not result or not result[0]:
        next_number = 1
    else:
        last_code = result[0]             # e.g. "SALE-0041"
        num = int(last_code.replace("SALE-", ""))
        next_number = num + 1

    order_code = f"SALE-{next_number:04d}"

    # =====================================================
    # PROCESS CART ITEMS
    # =====================================================
    total_sales = []

    for item in sale_data.items:

        # Get product for this business
        product = db.query(models.Product).filter(
            models.Product.name == item.product_name,
            models.Product.business_id == business_id
        ).first()

        if not product:
            raise HTTPException(status_code=404, detail=f"Product '{item.product_name}' not found")

        # Check stock
        if product.quantity < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Not enough stock for '{item.product_name}'"
            )

        # Calculate total price
        total_price = product.price * item.quantity

        # Reduce stock
        product.quantity -= item.quantity

        # Create the sale row
        sale = models.Sales(
            business_id=business_id,
            product_id=product.id,
            quantity=item.quantity,
            total_price=total_price,
            sale_code=order_code    # 👈 ONE order code for all items
        )

        db.add(sale)

        total_sales.append({
            "order_code": order_code,
            "product_name": product.name,
            "quantity_sold": item.quantity,
            "remaining_stock": product.quantity,
            "total_price": total_price
        })

    db.commit()

    return {
        "message": "✅ Sale recorded successfully!",
        "order_code": order_code,
        "items": total_sales
    }


# ======================================================
# GET SALES FOR THIS BUSINESS
# ======================================================
@router.get("/get_sales")
def get_sales(request: Request, db: Session = Depends(get_db)):

    current_user = verify_token(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Invalid token")

    business_id = current_user["business_id"]

    sales = db.query(models.Sales).filter(
        models.Sales.business_id == business_id
    ).all()

    result = []
    for sale in sales:
        result.append({
            "id": sale.id,
            "date": sale.created_at,
            "order_code": sale.sale_code,
            "product_name": sale.product.name if sale.product else "Unknown",
            "quantity": sale.quantity,
            "total_price": sale.total_price,
            "buying_price": sale.product.buying_price if sale.product else None
        })

    return result
