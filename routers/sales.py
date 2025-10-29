from fastapi import APIRouter, Depends, HTTPException, Form, Body, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from backend.db import SessionLocal
from backend import models
from pydantic import BaseModel
from typing import List
from backend.config import templates
router = APIRouter(prefix="/sales", tags=["sales"])


@router.get("/recordsale", response_class=HTMLResponse)
async def record_sale_page(request: Request):
    return templates.TemplateResponse("record_sale.html", {"request": request})

@router.get("/salesreport", response_class=HTMLResponse)
async def sales_report_page(request: Request):
    return templates.TemplateResponse("sales_report.html", {"request": request})

# Dependency for DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class SaleItem(BaseModel):
    product_name: str
    quantity: int

class SaleRequest(BaseModel):
    items: List[SaleItem]

@router.post("/record_sale/")
def record_sale(sale_data: SaleRequest, db: Session = Depends(get_db)):
    total_sales = []
    for item in sale_data.items:
        product = db.query(models.Product).filter(models.Product.name == item.product_name).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product '{item.product_name}' not found")

        if product.quantity < item.quantity:
            raise HTTPException(status_code=400, detail=f"Not enough stock for '{item.product_name}'")

        total_price = product.price * item.quantity
        product.quantity -= item.quantity

        sale = models.Sales(
            product_id=product.id,
            quantity=item.quantity,
            total_price=total_price
        )
        db.add(sale)
        db.commit()
        db.refresh(sale)

        total_sales.append({
            "sale_code": sale.sale_code,
            "product_name": product.name,
            "quantity_sold": item.quantity,
            "remaining_stock": product.quantity,
            "total_price": total_price
        })

    return {"message": "✅ Sales recorded successfully!", "sales": total_sales}
# ✅ Get all sales
@router.get("/get_sales")
def get_sales():
    db = SessionLocal()
    sales = db.query(models.Sales).all()

    result = []
    for sale in sales:
        result.append({
            "id": sale.id,
            "date": sale.created_at,
            "product_name": sale.product.name if sale.product else "Unknown",
            "quantity": sale.quantity,
            "total_price": sale.total_price
        })
    db.close()
    return result