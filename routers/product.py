from fastapi import APIRouter, Depends, HTTPException, Form, Body, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from backend.db import SessionLocal
from backend import models
from backend.config import templates
from backend.auth_utils import verify_token

router= APIRouter( prefix="/products", tags=["products"], dependencies=[Depends(verify_token)]  )


@router.get("/addproduct", response_class=HTMLResponse)
async def add_product_page(request: Request):
    return templates.TemplateResponse("add_product.html", {"request": request})

@router.get("/viewstocks", response_class=HTMLResponse)
async def view_stocks_page(request: Request):
    return templates.TemplateResponse("view_stock.html", {"request": request})


# Dependency for DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ✅ Add a new product (Form submission)
@router.post("/add_product")
def add_product(
    name: str = Form(...),
    price: float = Form(...),
    quantity: int = Form(...),
    current_user: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    try:
        new_product = models.Product(name=name, price=price, quantity=quantity, business_id=current_user["business_id"])
        db.add(new_product)
        db.commit()
        db.refresh(new_product)
        return {"message": f"✅ Product '{name}' added successfully!", "product": new_product.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# ✅ Get all products
def get_products(current_use: dict = Depends(verify_token), db: Session = Depends(get_db)):
    print("🔹 current_use =", current_use)
    business_id = current_use.get("business_id")

    if not business_id:
        print("❌ No business_id found in token!")
        raise HTTPException(status_code=401, detail="Not authenticated or no business ID")

    products = db.query(models.Product).filter(models.Product.business_id == business_id).all()
    print("✅ Found products:", products)
    return products

# ✅ Update stock quantity

@router.put("/update_stock/{product_id}")
def update_stock(product_id: int, data: dict = Body(...),current_user: dict =Depends(verify_token), db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id,models.Product.business_id ==current_user["business_id"]).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Safely update
    product.quantity = data.get("quantity", product.quantity)
    product.price = data.get("price", product.price)

    db.commit()
    db.refresh(product)
    return {"message": "✅ Product updated successfully", "product": product.name}
