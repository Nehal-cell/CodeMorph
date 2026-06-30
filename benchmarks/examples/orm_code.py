from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    name = Column(String(50))
    price = Column(Integer)

def get_product_price(session, product_name):
    product = session.query(Product).filter_by(name=product_name).first()
    if product:
        return product.price
    return None
