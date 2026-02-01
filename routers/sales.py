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
from backend.onboarding_utils import record_onboarding_event

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
    source = request.query_params.get("source")
    return templates.TemplateResponse(
        "record_sale.html",
        {"request": request, "source": source}
    )

@router.get("/salesreport", response_class=HTMLResponse)
async def sales_report_page(
    request: Request,
    current_user: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    record_onboarding_event(db, current_user["business_id"], "view_report")
    return templates.TemplateResponse("sales_report.html", {"request": request})

# -------------------------
# Input Models
# -------------------------
class SaleItem(BaseModel):
    product_name: str
    quantity: int
    selling_price: float

class SaleRequest(BaseModel):
    client_name: Optional[str] = None
    sales_person: Optional[str] = None
    items: List[SaleItem]

# =======================================================================
# 🚀 RECORD SALE
# =======================================================================
@router.post("/record_sale/")
def record_sale(sale_data: SaleRequest, request: Request, db: Session = Depends(get_db)):

    user = verify_token(request)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    business_id = user["business_id"]

    # --------------------------------------------------
    # ✅ NEW: detect onboarding source
    # --------------------------------------------------
    source = request.query_params.get("source")
    is_onboarding = (source == "onboarding")

    # --------------------------------------------------
    # ✅ NEW: check if business already has a REAL sale
    # --------------------------------------------------
    has_real_sale = (
        db.query(models.Sales)
        .join(models.Order, models.Sales.order_id == models.Order.id)
        .filter(
            models.Order.business_id == business_id,
            models.Sales.is_demo == False
        )
        .first()
    )

    # --------------------------------------------------
    # ✅ NEW: demo only if onboarding + no real sales yet
    # --------------------------------------------------
    is_demo_sale = (is_onboarding and has_real_sale is None)

    # --------------------------------------------------
    # ✅ NEW: if this is a REAL sale, delete any old demo sale rows
    # (demo will therefore also disappear from reports)
    # --------------------------------------------------
    if not is_demo_sale:
        db.query(models.Sales).join(models.Order).filter(
            models.Order.business_id == business_id,
            models.Sales.is_demo == True
        ).delete(synchronize_session=False)
        db.commit()

    # Generate order code (UNCHANGED)
    last_order = db.execute(
        text("SELECT id FROM orders ORDER BY id DESC LIMIT 1")
    ).fetchone()
    next_number = 1 if not last_order else last_order[0] + 1
    order_code = f"ORD-{next_number:05d}"

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
    total_profit = 0.0

    for item in sale_data.items:

        product = db.query(models.Product).filter(
            models.Product.name == item.product_name,
            models.Product.business_id == business_id
        ).first()

        if not product:
            raise HTTPException(
                status_code=404,
                detail=f"Product '{item.product_name}' not found"
            )

        # --------------------------------------------------
        # ✅ NEW: stock check ONLY for real sales
        # (demo sale should not scare them with stock issues)
        # --------------------------------------------------
        if not is_demo_sale:
            if product.quantity < item.quantity:
                raise HTTPException(
                    status_code=400,
                    detail=f"Not enough stock for '{item.product_name}'"
                )

        # Selling below buying price still blocked (UNCHANGED)
        if product.buying_price is not None and item.selling_price < product.buying_price:
            raise HTTPException(
                status_code=400,
                detail=f"Selling price for '{product.name}' cannot be below buying price"
            )

        subtotal = item.selling_price * item.quantity
        total_amount += subtotal

        # --------------------------------------------------
        # ✅ NEW: reduce stock ONLY for real sales
        # --------------------------------------------------
        if not is_demo_sale:
            product.quantity -= item.quantity

        bp = product.buying_price if product.buying_price is not None else 0
        total_profit += (item.selling_price - bp) * item.quantity

        sale_row = models.Sales(
            order_id=new_order.id,
            product_id=product.id,
            quantity=item.quantity,
            total_price=subtotal,
            is_demo=is_demo_sale  # ✅ NEW
        )
        db.add(sale_row)

    new_order.total_amount = total_amount
    db.commit()

    record_onboarding_event(db, business_id, "sell_product")

    # --------------------------------------------------
    # ✅ NEW: messaging
    # --------------------------------------------------
    message = "Order recorded successfully!"
    if is_demo_sale:
        message = (
            "Demo sale recorded successfully. "
            "Your stock was NOT reduced. "
            "When you record your next sale, this demo will be removed automatically."
        )

    return {
        "message": message,
        "order_code": order_code,
        "total_amount": total_amount,
        "total_profit": round(float(total_profit), 2),
        "is_demo": is_demo_sale
    }

# =======================================================================
# 🧾 SALES REPORT (DEMO VISIBLE)
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
        .filter(models.Order.business_id == business_id)  # ✅ unchanged: demo will show
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
            "subtotal": sale.total_price,
            "buying_price": product.buying_price or 0,
            "is_demo": getattr(sale, "is_demo", False)  # ✅ optional for UI badge
        })

    return output
