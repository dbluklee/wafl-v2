from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://wafl_user:wafl_password@localhost:55432/wafl_db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Store(Base):
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    store_name = Column(String(255), nullable=False)
    store_address = Column(String(500), nullable=False)
    business_number = Column(String(50), nullable=False, unique=True, index=True)
    owner_name = Column(String(100), nullable=False)
    owner_phone = Column(String(20), nullable=False)
    naver_store_url = Column(String(500))
    store_id = Column(String(50), index=True)

    # 스크래핑된 정보
    scraped_store_name = Column(String(255))
    scraped_category = Column(String(100))
    scraped_description = Column(Text)
    scraped_store_address = Column(String(500))
    scraped_directions = Column(Text)
    scraped_phone = Column(String(20))
    scraped_sns = Column(String(500))
    scraped_etc_info = Column(Text)
    scraped_intro = Column(Text)
    scraped_services = Column(Text)

    # 상태 관리
    scraping_status = Column(String(50), default='pending')
    scraping_error_message = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())