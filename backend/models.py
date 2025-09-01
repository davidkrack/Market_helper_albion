"""
Data models for Albion Market Helper
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class Region(str, Enum):
    WEST = "west"
    EUROPE = "europe"
    EAST = "east"

class Quality(int, Enum):
    NORMAL = 0
    GOOD = 1
    OUTSTANDING = 2
    EXCELLENT = 3
    MASTERPIECE = 4
    LEGENDARY = 5

class City(str, Enum):
    MARTLOCK = "Martlock"
    LYMHURST = "Lymhurst"
    BRIDGEWATCH = "Bridgewatch"
    THETFORD = "Thetford"
    FORT_STERLING = "Fort Sterling"
    CAERLEON = "Caerleon"

class PriceData(BaseModel):
    """Price data from AODP API"""
    item_id: str
    city: str
    quality: int = 0
    sell_price_min: Optional[float] = None
    sell_price_min_date: Optional[datetime] = None
    sell_price_max: Optional[float] = None
    sell_price_max_date: Optional[datetime] = None
    buy_price_min: Optional[float] = None
    buy_price_min_date: Optional[datetime] = None
    buy_price_max: Optional[float] = None
    buy_price_max_date: Optional[datetime] = None
    age_hours: Optional[float] = None  # Calculated field

class Opportunity(BaseModel):
    """Calculated market opportunity"""
    item_id: str
    item_name: Optional[str] = None
    quality: int = 0
    buy_city: str
    sell_city: str
    buy_price: float
    sell_price: float
    buy_timestamp: datetime
    sell_timestamp: datetime
    fees_percentage: float
    setup_fee: float
    transport_cost: float = 0
    profit_absolute: float
    profit_percentage: float
    is_caerleon_route: bool = False
    data_age_hours: float

class HistoricalDataPoint(BaseModel):
    """Historical price point"""
    timestamp: datetime
    item_count: int
    avg_price: float
    min_price: float
    max_price: float

class MarketSnapshot(BaseModel):
    """Complete market snapshot for caching"""
    timestamp: datetime
    region: str
    items: List[str]
    cities: List[str]
    prices: List[PriceData]
    ttl_seconds: int = 600