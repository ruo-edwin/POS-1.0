from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Boolean, func, UniqueConstraint, Numeric
)
from sqlalchemy.orm import relationship
from sqlalchemy import event
from backend.db import Base
from datetime import datetime

class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint('name', 'business_id', name='uq_product_name_business'),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True, nullable=False)
    business_id = Column(Integer, ForeignKey("business.id"), nullable=False)
    price = Column(Float, nullable=False)
    buying_price = Column(Float, nullable=True)
    quantity = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sales = relationship("Sales", back_populates="product")
    business = relationship("Business", back_populates="products")


class Sales(Base):
    __tablename__ = "sales"
    id = Column(Integer, primary_key=True, index=True)
    sale_code = Column(String(10), unique=True, index=True)
    business_id = Column(Integer, ForeignKey("business.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    total_price = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    product = relationship("Product", back_populates="sales")
    business = relationship("Business", back_populates="sales")


# Event listener to generate sale_code safely
@event.listens_for(Sales, "before_insert")
def generate_sale_code(mapper, connection, target):
    if not target.sale_code:
        last_id = connection.execute(
            f"SELECT id FROM sales ORDER BY id DESC LIMIT 1"
        ).fetchone()
        next_number = 1 if not last_id else last_id[0] + 1
        target.sale_code = f"SALE-{next_number:04d}"


class Business(Base):
    __tablename__ = "business"
    id = Column(Integer, primary_key=True, index=True)
    business_code = Column(String(20), unique=True, index=True)
    business_name = Column(String(100), nullable=False)
    username = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    phone = Column(String(20))
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    users = relationship("User", back_populates="business")
    products = relationship("Product", back_populates="business")
    sales = relationship("Sales", back_populates="business")
    subscription = relationship("Subscription", back_populates="business", uselist=False)



class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("business.id"), nullable=False)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)  # e.g., 'admin', 'staff'
    is_active = Column(Boolean, default=False)  # True for active, False for inactive
    last_login = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    business = relationship("Business", back_populates="users")



class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("business.id"), nullable=False)

    plan_name = Column(String(50), default="monthly")  # demo / monthly / yearly (future)
    amount = Column(Numeric(10,2), default=0)

    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime)  # demo expiry OR paid expiry

    status = Column(String, default="demo")  
    # demo, active, expired, suspended

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    business = relationship("Business", back_populates="subscription")
