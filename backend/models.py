from sqlalchemy import Column, Integer, String,Float, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.db import Base

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name =Column(String(255), unique=True, index=True, nullable=False)
    business_id =Column(Integer, ForeignKey("business.id"), nullable=False)
    price =Column(Float, nullable=False)
    buying_price =Column(Float, nullable=False)
    quantity =Column(Integer, default=0)
    created_at =Column(DateTime, default=datetime.utcnow)
    
    sales =relationship("Sales", back_populates="product")
    business =relationship("Business", back_populates="products")


class Sales(Base):
    __tablename__ = "sales"
    id = Column(Integer, primary_key=True, index=True)
    sale_code =Column(String(10), unique=True, index=True)
    business_id =Column(Integer, ForeignKey("business.id"), nullable=False)
    product_id =Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity =Column(Integer, nullable=False)
    total_price =Column(Float, nullable=False)
    created_at =Column(DateTime, default=datetime.utcnow)

    product =relationship("Product", back_populates="sales")
    business=relationship("Business", back_populates="sales")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.sale_code:
            from sqlalchemy.orm.session import object_session
            session = object_session(self)
            if session:
                last_sale = session.query(Sales).order_by(Sales.id.desc()).first()
                next_number = 1 if not last_sale else last_sale.id + 1
                self.sale_code = f"SALE-{next_number:04d}"

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

    # Relationship: one business → many users
    users = relationship("User", back_populates="business")
    products = relationship("Product", back_populates="business")
    sales = relationship("Sales", back_populates="business")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("business.id"), nullable=False)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)  # e.g., 'admin', 'staff'
    is_active = Column(Integer, default=0)  # 1 for active, 0 for inactive
    last_login = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship: many users → one business
    business = relationship("Business", back_populates="users")