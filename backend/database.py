"""
Database models and setup for private market data ingestion
"""

from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, Index, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./albion_market.db")

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class
Base = declarative_base()

class MarketTick(Base):
    """Market data tick from either PRIVATE (ADC) or AODP source"""
    __tablename__ = "market_ticks"
    
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False)  # 'PRIVATE' or 'AODP'
    region = Column(String, nullable=False)
    city = Column(String, nullable=False)
    item_id = Column(String, nullable=False)
    quality = Column(Integer, default=0)
    
    # Prices
    sell_price_min = Column(Float, nullable=True)
    sell_price_max = Column(Float, nullable=True)
    buy_price_min = Column(Float, nullable=True)
    buy_price_max = Column(Float, nullable=True)
    
    # Timestamps
    timestamp = Column(DateTime, nullable=False)
    ingested_at = Column(DateTime, default=datetime.utcnow)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_lookup', 'city', 'item_id', 'quality', 'source'),
        Index('idx_timestamp', 'timestamp'),
        Index('idx_ingested', 'ingested_at'),
        # Unique constraint for deduplication
        UniqueConstraint('city', 'item_id', 'quality', 'timestamp', 'source', name='uq_market_tick'),
    )

class IngestStats(Base):
    """Statistics for monitoring ingestion"""
    __tablename__ = "ingest_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False)
    last_ingest_at = Column(DateTime)
    total_records = Column(Integer, default=0)
    daily_records = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Create tables
def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()