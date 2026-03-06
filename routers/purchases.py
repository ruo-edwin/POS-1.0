from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from backend.db import SessionLocal
from backend import models
from backend.config import templates
from backend.auth_utils import verify_token
from backend.template_context import base_context

router = APIRouter(prefix="/purchases", tags=["purchases"], dependencies=[Depends(verify_token)])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------------------
# PAGE: Receive Stock
# ---------------------------
@router.get("/receive", response_class=HTMLResponse)
def receive_stock_page(
    request: Request,
    current_user: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    if not current_user or current_user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Access denied")

    user = db.query(models.User).filter(models.User.id == current_user["user_id"]).first()

    return templates.TemplateResponse(
        "purchases.html",
        {
            **base_context(request, user),
            "active_page": "purchases"
        }
    )

# ---------------------------
# API: Fetch suppliers
# ---------------------------
@router.get("/suppliers")
def list_suppliers(
    request: Request,
    current_user: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    suppliers = db.query(models.Supplier).filter(
        models.Supplier.business_id == current_user["business_id"]
    ).order_by(models.Supplier.name.asc()).all()

    return [{"id": s.id, "name": s.name} for s in suppliers]

# ---------------------------
# API: Fetch products
# ---------------------------
@router.get("/products")
def list_products(
    request: Request,
    current_user: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    products = db.query(models.Product).filter(
        models.Product.business_id == current_user["business_id"]
    ).order_by(models.Product.name.asc()).all()

    return [{"id": p.id, "name": p.name, "price": p.price, "buying_price": p.buying_price, "quantity": p.quantity} for p in products]

# ---------------------------
# SUBMIT RECEIVE STOCK
# ---------------------------
class ReceiveItem(BaseModel):
    product_id: int
    quantity: int
    buying_price: Optional[float] = None
    selling_price: Optional[float] = None

class ReceiveStockRequest(BaseModel):
    supplier_id: Optional[int] = None
    invoice_number: Optional[str] = None
    notes: Optional[str] = None
    items: List[ReceiveItem]

@router.post("/receive_submit")
def receive_stock_submit(
    payload: ReceiveStockRequest,
    request: Request,
    current_user: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    if not current_user or current_user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Access denied")

    business_id = current_user["business_id"]
    user_id = current_user["user_id"]

    if not payload.items or len(payload.items) == 0:
        raise HTTPException(status_code=400, detail="Add at least one item")

    # Validate supplier belongs to same business (if provided)
    if payload.supplier_id:
        supplier = db.query(models.Supplier).filter(
            models.Supplier.id == payload.supplier_id,
            models.Supplier.business_id == business_id
        ).first()
        if not supplier:
            raise HTTPException(status_code=400, detail="Invalid supplier")

    try:
        purchase = models.Purchase(
            business_id=business_id,
            supplier_id=payload.supplier_id,
            invoice_number=payload.invoice_number,
            notes=payload.notes,
            created_by=user_id,
            total_amount=0
        )
        db.add(purchase)
        db.flush()  # gives purchase.id before commit

        total_amount = 0.0

        for item in payload.items:
            if item.quantity <= 0:
                continue

            product = db.query(models.Product).filter(
                models.Product.id == item.product_id,
                models.Product.business_id == business_id
            ).first()

            if not product:
                raise HTTPException(status_code=404, detail=f"Product not found (id={item.product_id})")

            # ✅ Update stock
            product.quantity += item.quantity

            # ✅ Professional rule (your chosen direction):
            # When new stock comes with new buying/selling price, we update the product master prices.
            if item.buying_price is not None:
                product.buying_price = float(item.buying_price)

            if item.selling_price is not None:
                product.price = float(item.selling_price)

            line_total = 0.0
            if item.buying_price is not None:
                line_total = float(item.buying_price) * item.quantity

            total_amount += line_total

            purchase_item = models.PurchaseItem(
                purchase_id=purchase.id,
                product_id=product.id,
                quantity=item.quantity,
                buying_price=item.buying_price,
                line_total=line_total
            )
            db.add(purchase_item)

            movement = models.InventoryMovement(
                business_id=business_id,
                product_id=product.id,
                movement_type="purchase",
                quantity=item.quantity,           # positive = stock in
                reference_id=purchase.id,
                reason=f"Receive Stock ({payload.invoice_number or 'No Invoice'})",
                created_by=user_id
            )
            db.add(movement)

        purchase.total_amount = round(total_amount, 2)

        db.commit()

        return {"message": "✅ Stock received successfully", "purchase_id": purchase.id, "total": purchase.total_amount}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))