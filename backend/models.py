from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Boolean, func, UniqueConstraint, Numeric, Text
)
from sqlalchemy.orm import relationship, validates
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
     
    @validates("price")
    def validate_price(self, key, value):
        if self.buying_price is not None and value < self.buying_price:
            raise ValueError("Selling price cannot be below buying price")
        return value

        
    sales = relationship("Sales", back_populates="product")
    business = relationship("Business", back_populates="products")


class Sales(Base):
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    total_price = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_demo = Column(Boolean, default=False, nullable=False)

    product = relationship("Product")
    order = relationship("Order", back_populates="sales")


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
    subscription = relationship("Subscription", back_populates="business", uselist=False)
    orders = relationship("Order", back_populates="business")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("business.id"), nullable=True)
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
    business_id = Column(Integer, ForeignKey("business.id"), nullable=True)

    plan_name = Column(String(50), default="monthly")  # demo / monthly / yearly (future)
    amount = Column(Numeric(10,2), default=0)

    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime)  # demo expiry OR paid expiry

    status = Column(String(50), default="demo")  
    # demo, active, expired, suspended

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    business = relationship("Business", back_populates="subscription")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_code = Column(String(20), unique=True, index=True)
    business_id = Column(Integer, ForeignKey("business.id"), nullable=False)

    client_name = Column(String(100), nullable=True)
    sales_person = Column(String(100), nullable=True)

    total_amount = Column(Float, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    business = relationship("Business", back_populates="orders")
    sales = relationship("Sales", back_populates="order")

class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    business_id = Column(Integer, nullable=False, index=True)

    endpoint = Column(Text, nullable=False)
    p256dh = Column(String(255), nullable=False)
    auth = Column(String(255), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

class OnboardingEvent(Base):
    __tablename__ = "onboarding_events"

    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, ForeignKey("business.id"), index=True)
    event = Column(String(50), index=True)  # e.g. view_stock, view_report
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("business_id", "event", name="uq_onboarding_event"),
    )