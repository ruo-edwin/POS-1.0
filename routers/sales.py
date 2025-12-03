from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import List, Optional

from backend.db import SessionLocal
from backend import models
from backend.config import templates
from backend.auth_utils import verify_token


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
# Input Models
# -------------------------
class SaleItem(BaseModel):
    product_name: str
    quantity: int


class SaleRequest(BaseModel):
    client_name: Optional[str] = None
    sales_person: Optional[str] = None
    items: List[SaleItem]


# =======================================================================
# 🚀 RECORD SALE — CREATE ORDER & ITEMS
# =======================================================================
@router.post("/record_sale/")
def record_sale(sale_data: SaleRequest, request: Request, db: Session = Depends(get_db)):

    user = verify_token(request)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    business_id = user["business_id"]

    # Generate order code
    last_order = db.execute(text("SELECT id FROM orders ORDER BY id DESC LIMIT 1")).fetchone()
    next_number = 1 if not last_order else last_order[0] + 1
    order_code = f"ORD-{next_number:05d}"

    # Create order
    new_order = models.Order(
        order_code=order_code,
        business_id=business_id,
        client_name=sale_data.client_name,
        sales_person=sale_data.sales_person,
        total_amount=0
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    total_amount = 0
    output_items = []

    # Process items
    for item in sale_data.items:

        product = db.query(models.Product).filter(
            models.Product.name == item.product_name,
            models.Product.business_id == business_id
        ).first()

        if not product:
            raise HTTPException(status_code=404, detail=f"Product '{item.product_name}' not found")

        if product.quantity < item.quantity:
            raise HTTPException(status_code=400, detail=f"Not enough stock for '{item.product_name}'")

        subtotal = product.price * item.quantity
        product.quantity -= item.quantity
        total_amount += subtotal

        sale_row = models.Sales(
            order_id=new_order.id,
            product_id=product.id,
            quantity=item.quantity,
            total_price=subtotal
        )
        db.add(sale_row)

        output_items.append({
            "product": product.name,
            "quantity": item.quantity,
            "subtotal": subtotal
        })

    new_order.total_amount = total_amount
    db.commit()

    return {
        "message": "Order recorded successfully!",
        "order_code": order_code,
        "client_name": new_order.client_name,
        "sales_person": new_order.sales_person,
        "total_amount": total_amount,
        "items": output_items
    }


# =======================================================================
# 🧾 ORDER-WISE SALES REPORT
# =======================================================================
@router.get("/get_sales")
def get_sales(request: Request, db: Session = Depends(get_db)):

    user = verify_token(request)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    business_id = user["business_id"]

    orders = db.query(models.Order).filter(
        models.Order.business_id == business_id
    ).order_by(models.Order.id.desc()).all()

    final_output = []

    for order in orders:
        order_items = []

        for sale in order.sales:  # FIXED
            order_items.append({
                "product_name": sale.product.name,
                "quantity": sale.quantity,
                "subtotal": sale.total_price
            })

        final_output.append({
            "order_code": order.order_code,
            "date": order.created_at,
            "client_name": order.client_name,
            "sales_person": order.sales_person,
            "total_amount": order.total_amount,
            "items": order_items
        })

    return final_output


# =======================================================================
# 📌 ITEM-WISE SALES REPORT (Flat list)
# =======================================================================
@router.get("/get_sales_items")
def get_sales_items(request: Request, db: Session = Depends(get_db)):

    user = verify_token(request)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    business_id = user["business_id"]

    sales_items = (
        db.query(models.Sales, models.Order, models.Product)
        .join(models.Order, models.Sales.order_id == models.Order.id)
        .join(models.Product, models.Sales.product_id == models.Product.id)
        .filter(models.Order.business_id == business_id)
        .order_by(models.Sales.id.desc())
        .all()
    )

    output = []

    for sale, order, product in sales_items:
        output.append({
            "order_code": order.order_code,
            "date": order.created_at,
            "client_name": order.client_name,
            "sales_person": order.sales_person,
            "product_name": product.name,
            "quantity": sale.quantity,
            "subtotal": sale.total_price
        })

    return output
