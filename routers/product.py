from fastapi import APIRouter, Depends, HTTPException, Form, Body, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from backend.db import SessionLocal
from backend import models
from backend.config import templates
from backend.auth_utils import verify_token
from backend.onboarding_utils import record_onboarding_event
from backend.template_context import base_context
from datetime import datetime

# ✅ Define base URL for production (Railway)
BASE_URL = "https://pos-10-production.up.railway.app"

router = APIRouter(
    prefix="/products",
    tags=["products"],
    dependencies=[Depends(verify_token)]
)

# ---------------- DB DEPENDENCY ----------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------- HTML ROUTES ----------------

@router.get("/addproduct", response_class=HTMLResponse)
async def add_product_page(request: Request):
    # ✅ NEW: admin/manager only
    current_user = verify_token(request)
    if not current_user or current_user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Access denied")

    # ✅ capture onboarding source so the template (or redirects) can use it
    source = request.query_params.get("source")  # "onboarding" or None
    return templates.TemplateResponse("add_product.html", {"request": request, "source": source})


@router.get("/adjust/{product_id}", response_class=HTMLResponse)
async def adjust_stock_page(
    product_id: int,
    request: Request,
    current_user: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    # ✅ admin/manager only
    if not current_user or current_user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Access denied")

    product = db.query(models.Product).filter(
        models.Product.id == product_id,
        models.Product.business_id == current_user["business_id"]
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    user_obj = db.query(models.User).filter(models.User.id == current_user["user_id"]).first()

    return templates.TemplateResponse(
        "adjust_stock.html",
        {
            **base_context(request, user_obj),
            "active_page": "products",
            "product": product
        }
    )
@router.get("/viewstocks", response_class=HTMLResponse)
async def view_stocks_page(
    request: Request,
    current_user: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    # ✅ NEW: admin/manager only
    if not current_user or current_user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Access denied")

    # ✅ Stock page still exists, but we are NOT tracking it as an onboarding step anymore
    return templates.TemplateResponse("view_stock.html", {"request": request})
@router.get("/history/{product_id}", response_class=HTMLResponse)
async def product_history(
    product_id: int,
    request: Request,
    current_user: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):

    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    product = db.query(models.Product).filter(
        models.Product.id == product_id,
        models.Product.business_id == current_user["business_id"]
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    movements = db.query(models.InventoryMovement).filter(
        models.InventoryMovement.product_id == product_id,
        models.InventoryMovement.business_id == current_user["business_id"]
    ).order_by(models.InventoryMovement.created_at.desc()).all()

    return templates.TemplateResponse(
        "product_history.html",
        {
            "request": request,
            "product": product,
            "movements": movements
        }
    )
# ---------------- ADD PRODUCT ----------------

@router.post("/add_product")
def add_product(
    request: Request,  # ✅ add request so we can read ?source=onboarding
    name: str = Form(...),
    price: float = Form(...),
    buying_price: float = Form(...),
    quantity: int = Form(...),
    current_user: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    # ✅ NEW: admin/manager only
    if not current_user or current_user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        new_product = models.Product(
            name=name,
            price=price,
            buying_price=buying_price,
            quantity=quantity,
            business_id=current_user["business_id"]
        )
        db.add(new_product)
        db.commit()
        db.refresh(new_product)

        # ✅ mark onboarding event (safe because of unique constraint)
        record_onboarding_event(db, current_user["business_id"], "add_product")

        # ✅ If they came from onboarding flow, redirect straight to record sale
        source = request.query_params.get("source")
        if source == "onboarding":
            return RedirectResponse(url=f"{BASE_URL}/sales/recordsale?source=onboarding", status_code=303)

        # ✅ normal API behavior stays the same
        return {"message": f"✅ Product '{name}' added successfully!", "product": new_product.id}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# ---------------- GET ALL PRODUCTS ----------------

@router.get("/")
def get_products(current_use: dict = Depends(verify_token), db: Session = Depends(get_db)):
    print("🔹 current_use =", current_use)
    business_id = current_use.get("business_id")

    if not business_id:
        print("❌ No business_id found in token!")
        # Redirect to login if user is not authenticated
        return RedirectResponse(url=f"{BASE_URL}/auth/login")

    products = db.query(models.Product).filter(models.Product.business_id == business_id).all()
    print("✅ Found products:", products)
    return products

# ---------------- UPDATE STOCK ----------------

@router.put("/update_stock/{product_id}")
def update_stock(
    product_id: int,
    data: dict = Body(...),
    current_user: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    # ✅ NEW: admin/manager only
    if not current_user or current_user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Access denied")

    product = db.query(models.Product).filter(
        models.Product.id == product_id,
        models.Product.business_id == current_user["business_id"]
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Update fields
    product.quantity = data.get("quantity", product.quantity)
    product.price = data.get("price", product.price)
    product.buying_price = data.get("buying_price", product.buying_price)

    db.commit()
    db.refresh(product)
    return {"message": "✅ Product updated successfully", "product": product.name}

@router.post("/adjust/{product_id}")
async def adjust_stock_submit(
    product_id: int,
    request: Request,
    action: str = Form(...),   # "increase" or "decrease"
    qty: int = Form(...),
    reason: str = Form(""),
    current_user: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    # ✅ admin/manager only
    if not current_user or current_user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Access denied")

    if qty is None or qty <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than 0")

    if action not in ["increase", "decrease"]:
        raise HTTPException(status_code=400, detail="Invalid action")

    product = db.query(models.Product).filter(
        models.Product.id == product_id,
        models.Product.business_id == current_user["business_id"]
    ).with_for_update().first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    signed_qty = qty if action == "increase" else -qty

    # ✅ Block negative stock (recommended)
    if product.quantity + signed_qty < 0:
        raise HTTPException(status_code=400, detail="Cannot reduce below 0 stock")

    try:
        # 1) Write movement (ledger)
        mv = models.InventoryMovement(
            product_id=product.id,
            business_id=current_user["business_id"],
            movement_type="adjustment",
            quantity=signed_qty,
            reference_id=None,
            reason=(reason.strip() or None),
            created_at=datetime.utcnow()
        )
        db.add(mv)

        # 2) Update cached stock
        product.quantity = product.quantity + signed_qty

        db.commit()

        return RedirectResponse(url="/products/viewstocks", status_code=303)

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))